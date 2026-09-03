"""A genuine LLM-backed agent provider: Anthropic's Messages API called
directly over HTTP (httpx — already a project dependency; no `anthropic`
SDK needed). Exposes the agent's READ tools (app/agent/tools.py) through
Anthropic's tool-use feature and runs a bounded loop
(`settings.max_agent_tool_calls`) until the model calls the terminal
`submit_decision` tool.

Never given WRITE tools — this provider can reason and select, never
execute. Never fails silently: any malformed response, HTTP failure, or
loop exhaustion raises AgentProviderError, which the caller
(app/services/agent_service.py) catches and falls back to the
deterministic engine — the system stays fully functional either way.
"""

import json

import httpx

from app.agent.provider import AgentProvider, AgentProviderError
from app.agent.tools import READ_TOOL_SPECS, ToolError, call_tool
from app.agent.types import DecisionContext, ProviderDecision, ToolContext

PROVIDER_NAME = "anthropic-claude"

SUBMIT_DECISION_TOOL = {
    "name": "submit_decision",
    "description": "Submit your final recovery decision for this case. Call this exactly once, when "
    "ready to conclude. selected_action must be one of the action types listed in the case context "
    "as currently allowed, or null if none are safe to select.",
    "input_schema": {
        "type": "object",
        "properties": {
            "selected_action": {
                "type": ["string", "null"],
                "description": "One of the allowed action types, or null if no safe action exists.",
            },
            "reasoning_summary": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "requires_human_review": {"type": "boolean"},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["selected_action", "reasoning_summary", "confidence", "requires_human_review"],
    },
}

SYSTEM_PROMPT = (
    "You are RecoverAI's recovery-decision agent. You analyze a failed payment case and select ONE "
    "recovery action from a fixed, policy-pre-filtered list — you never invent a new action, never "
    "estimate financial figures yourself (probability and expected value are already computed and "
    "given to you), and never execute anything. A separate, independent server-side step re-validates "
    "and executes your selection; nothing you say authorizes it directly. Be concise and specific."
)


def _read_tool_schemas() -> list[dict]:
    return [
        {"name": spec.name, "description": spec.description, "input_schema": spec.input_model.model_json_schema()}
        for spec in READ_TOOL_SPECS
    ]


# Only read tools (plus submit_decision, handled separately) are ever
# offered to this provider's tools list below — this is the corresponding
# server-side enforcement: even if a response names any other tool
# (e.g. a write tool that exists in the shared TOOL_REGISTRY but was
# never advertised here), it is rejected, never executed. Defense in
# depth against a malformed, hallucinating, or manipulated model response.
_OFFERED_TOOL_NAMES = frozenset(spec.name for spec in READ_TOOL_SPECS)


def _context_to_prompt(context: DecisionContext) -> str:
    if context.available_actions:
        allowed = "\n".join(
            f"  - {a.action_type}: expected value {a.expected_value_cents / 100:.2f} "
            f"{context.currency.upper()} ({a.reason_code}: {a.message})"
            for a in context.available_actions
        )
    else:
        allowed = "  (none — no automated action is currently permitted)"

    probability_line = (
        f"{context.recovery_probability:.0%} ({context.confidence_band} confidence, model {context.model_version})"
        if context.recovery_probability is not None
        else "not available"
    )

    return (
        f"Case #{context.case_id} — {context.case_status}.\n"
        f"Amount at risk: {context.amount_at_risk_cents / 100:.2f} {context.currency.upper()}.\n"
        f"Decline: {context.decline_class} / {context.decline_code} — {context.diagnosis_explanation}\n"
        f"Recovery probability: {probability_line}.\n"
        f"Customer: {context.customer_plan_tier} tier, {context.customer_tenure_days:.0f} days tenure, "
        f"{context.customer_prior_recovery_rate:.0%} historical recovery rate.\n"
        f"Retries so far on this case: {context.executed_retry_count}. Prior failed attempts on this "
        f"case: {context.prior_failed_attempts_on_case}.\n"
        f"Policy version: {context.policy_version}.\n"
        f"Currently allowed actions (you may ONLY select from this list, or null):\n{allowed}\n\n"
        "You may call the read-only tools below to look deeper before deciding. You have no tool "
        "that writes or executes anything. When ready, call submit_decision exactly once."
    )


class AnthropicAgentProvider(AgentProvider):
    name = PROVIDER_NAME
    mode = "llm"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_base: str,
        timeout_seconds: float,
        max_tool_calls: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout_seconds
        self._max_tool_calls = max_tool_calls
        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def generate_decision(self, context: DecisionContext, tool_context: ToolContext) -> ProviderDecision:
        messages: list[dict] = [{"role": "user", "content": _context_to_prompt(context)}]
        tools = [*_read_tool_schemas(), SUBMIT_DECISION_TOOL]

        for _ in range(self._max_tool_calls):
            response = self._call_api(messages, tools)
            content_blocks = response.get("content", [])
            tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]

            if not tool_use_blocks:
                raise AgentProviderError("Anthropic response contained no tool_use block — cannot extract a decision.")

            messages.append({"role": "assistant", "content": content_blocks})

            decision = None
            tool_results = []
            for block in tool_use_blocks:
                tool_name = block.get("name")
                if tool_name == "submit_decision":
                    decision = self._parse_decision(block.get("input") or {}, context)
                    break
                try:
                    if tool_name not in _OFFERED_TOOL_NAMES:
                        raise ToolError(
                            "tool_not_offered",
                            f"'{tool_name}' was not offered in this call and cannot be invoked. Only "
                            "the read-only tools listed, plus submit_decision, are available.",
                        )
                    result = call_tool(tool_context, tool_name, block.get("input") or {})
                    output = result.model_dump()
                except ToolError as exc:
                    output = {"error": exc.code, "message": exc.message}
                except Exception as exc:  # noqa: BLE001 - a tool failure must never crash the agent loop
                    output = {"error": "tool_execution_failed", "message": str(exc)}
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(output)}
                )

            if decision is not None:
                return decision
            if not tool_results:
                raise AgentProviderError("Model made no usable tool call and did not submit a decision.")
            messages.append({"role": "user", "content": tool_results})

        raise AgentProviderError(
            f"Exceeded the maximum of {self._max_tool_calls} tool-call turns without a final decision."
        )

    def _call_api(self, messages: list[dict], tools: list[dict]) -> dict:
        try:
            resp = self._client.post(
                f"{self._api_base}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": self._model, "max_tokens": 1024, "system": SYSTEM_PROMPT, "messages": messages, "tools": tools},
            )
        except httpx.HTTPError as exc:
            raise AgentProviderError(f"Anthropic API request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AgentProviderError(f"Anthropic API returned HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise AgentProviderError(f"Anthropic API returned a non-JSON response: {exc}") from exc

    def _parse_decision(self, raw: dict, context: DecisionContext) -> ProviderDecision:
        try:
            selected_action = raw.get("selected_action")
            reasoning_summary = raw["reasoning_summary"]
            confidence = float(raw["confidence"])
            requires_human_review = bool(raw["requires_human_review"])
            risk_flags = list(raw.get("risk_flags") or [])
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentProviderError(f"Malformed submit_decision payload: {exc}") from exc

        if selected_action is not None and selected_action not in context.action_types():
            raise AgentProviderError(
                f"Model selected '{selected_action}', which is not in the policy-allowed set "
                f"{context.action_types()}."
            )
        if not (0.0 <= confidence <= 1.0):
            raise AgentProviderError(f"Confidence {confidence} is outside [0, 1].")

        return ProviderDecision(
            selected_action=selected_action,
            reasoning_summary=reasoning_summary,
            confidence=confidence,
            requires_human_review=requires_human_review,
            risk_flags=risk_flags,
        )
