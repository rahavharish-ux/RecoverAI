"""The default, always-available decision engine — no LLM call, no
network, no API key required. Picks the highest-expected-value allowed
action and produces a templated (not model-generated) reasoning summary.

Labeled "Deterministic Decision Engine" everywhere it's surfaced (see
AgentMode.DETERMINISTIC) — it is never presented as, or mistaken for, an
LLM's output."""

from app.agent.provider import AgentProvider
from app.agent.types import DecisionContext, ProviderDecision, ToolContext

PROVIDER_NAME = "deterministic-v1"


class DeterministicDecisionEngine(AgentProvider):
    name = PROVIDER_NAME
    mode = "deterministic"

    def generate_decision(self, context: DecisionContext, tool_context: ToolContext | None = None) -> ProviderDecision:
        if not context.available_actions:
            return ProviderDecision(
                selected_action=None,
                reasoning_summary="No policy-allowed action remains for this case — no automated "
                "decision can be made; this case requires human review.",
                confidence=1.0,
                requires_human_review=True,
                risk_flags=["no_allowed_actions"],
            )

        best = max(context.available_actions, key=lambda a: a.expected_value_cents)
        probability_note = (
            f"the calibrated model estimates a {context.recovery_probability:.0%} recovery probability "
            f"({context.confidence_band} confidence)"
            if context.recovery_probability is not None
            else "no recovery-probability estimate is currently available for this case"
        )
        reasoning = (
            f"This failure is diagnosed as a {context.decline_class} decline ({context.decline_code}). "
            f"{probability_note}. Among the {len(context.available_actions)} action(s) policy currently "
            f"allows, '{best.action_type}' has the highest expected value "
            f"({best.expected_value_cents / 100:.2f} {context.currency.upper()}). Selecting it."
        )
        confidence = context.recovery_probability if context.recovery_probability is not None else 0.5
        return ProviderDecision(
            selected_action=best.action_type,
            reasoning_summary=reasoning,
            confidence=confidence,
            requires_human_review=False,  # deterministic risk flags are OR'd in by the caller regardless
            risk_flags=[],
        )
