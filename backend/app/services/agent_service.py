"""The DECIDE stage's orchestrator, and the EXECUTE stage that follows it.

DECIDE gathers a DecisionContext through the agent's read tools
(app/agent/tools.py), asks a provider (LLM if configured, else the
deterministic engine — see app/agent/) to select ONE action from the
already policy-filtered list, ORs in server-computed risk flags the
provider cannot weaken, and persists the result. Nothing here writes to
`cases` or `actions`.

EXECUTE never trusts a decision as authorization by itself: it re-fetches
the case, re-runs policy, and re-checks idempotency by calling straight
into Phase 1's unmodified `action_service.request_action` — the exact same
gate a human clicking "retry" in the API goes through. An agent's earlier
reasoning changes nothing about what's allowed the moment execution runs.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agent.deterministic_provider import DeterministicDecisionEngine
from app.agent.provider import AgentProvider, AgentProviderError
from app.agent.risk import compute_deterministic_risk_flags
from app.agent.tools import TOOL_REGISTRY
from app.agent.types import AvailableAction, DecisionContext, ProviderDecision, ToolContext
from app.core.config import get_settings
from app.domain.enums import ActionType, AgentMode, CaseEventType, DecisionStatus
from app.integrations.payment_gateway import PaymentGatewayPort
from app.models.actions import Action, ActionOutcome
from app.models.agent import AgentDecision, AgentToolCall
from app.models.cases import Case, PolicyDecision
from app.models.payments import PaymentAttempt
from app.services import action_service, audit_service, case_query
from app.services.action_service import ActionNotEligible

logger = logging.getLogger(__name__)


class AgentDecisionNotExecutable(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _select_provider(settings) -> tuple[AgentProvider, AgentMode]:
    if settings.anthropic_api_key:
        from app.agent.anthropic_provider import AnthropicAgentProvider

        provider = AnthropicAgentProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            api_base=settings.anthropic_api_base,
            timeout_seconds=settings.anthropic_timeout_seconds,
            max_tool_calls=settings.max_agent_tool_calls,
        )
        return provider, AgentMode.LLM
    return DeterministicDecisionEngine(), AgentMode.DETERMINISTIC


def _run_read_tool(tool_ctx: ToolContext, name: str) -> object:
    spec = TOOL_REGISTRY[name]
    return spec.handler(tool_ctx, spec.input_model())


def _build_context(db: Session, case: Case) -> tuple[DecisionContext, list[tuple[str, dict, dict]]]:
    settings = get_settings()
    tool_ctx = ToolContext(db=db, case=case)
    calls: list[tuple[str, dict, dict]] = []

    def run(name: str):
        result = _run_read_tool(tool_ctx, name)
        calls.append((name, {}, result.model_dump()))
        return result

    run("get_transaction")
    history = run("get_customer_history")
    failure = run("analyze_payment_failure")
    probability = run("calculate_recovery_probability")
    run("check_retry_eligibility")
    policy = run("get_recovery_policy")
    state = run("get_case_state")
    values = run("calculate_expected_recovery_value")

    available_actions = [
        AvailableAction(
            action_type=e.action_type,
            reason_code=e.reason_code,
            message=e.message,
            expected_value_cents=values.expected_values_cents.get(e.action_type, 0),
        )
        for e in policy.eligibilities
        if e.allowed
    ]

    context = DecisionContext(
        case_id=case.id,
        case_status=state.status,
        amount_at_risk_cents=state.amount_at_risk_cents,
        currency=case.currency,
        decline_code=failure.decline_code,
        decline_class=failure.decline_class,
        diagnosis_explanation=failure.explanation,
        recovery_probability=probability.recovery_probability,
        confidence_band=probability.confidence_band,
        model_version=probability.model_version,
        top_contributions=[],
        customer_plan_tier=history.plan_tier,
        customer_tenure_days=history.tenure_days,
        customer_prior_recovery_rate=history.prior_recovery_rate,
        prior_failed_attempts_on_case=case_query.failed_attempt_count_for_case(db, case.id),
        executed_retry_count=case_query.executed_action_count_for_case(db, case.id),
        policy_version=policy.policy_version,
        available_actions=available_actions,
        generated_at=datetime.now(timezone.utc),
    )
    _ = settings  # reserved for future context enrichment
    return context, calls


def decide(db: Session, *, case: Case, provider_override: AgentProvider | None = None) -> AgentDecision:
    settings = get_settings()
    context, tool_calls = _build_context(db, case)

    existing_count = db.query(AgentDecision).filter(AgentDecision.case_id == case.id).count()

    if existing_count >= settings.max_agent_decisions_per_case:
        decision_result = ProviderDecision(
            selected_action=None,
            reasoning_summary=f"This case has reached the maximum of {settings.max_agent_decisions_per_case} "
            "automated decisions. Further automated reasoning is refused — this case must be handled by "
            "a human.",
            confidence=1.0,
            requires_human_review=True,
            risk_flags=["max_decisions_reached"],
        )
        provider_name, agent_mode = "agent-service-guard", AgentMode.DETERMINISTIC
    else:
        tool_ctx = ToolContext(db=db, case=case)
        if provider_override is not None:
            provider = provider_override
            agent_mode = AgentMode(provider.mode)
        else:
            provider, agent_mode = _select_provider(settings)
        try:
            decision_result = provider.generate_decision(context, tool_ctx)
            provider_name = provider.name
        except AgentProviderError as exc:
            logger.warning("Agent provider %s failed (%s) — falling back to the deterministic engine.", provider.name, exc)
            fallback = DeterministicDecisionEngine()
            decision_result = fallback.generate_decision(context, tool_ctx)
            provider_name, agent_mode = fallback.name, AgentMode.DETERMINISTIC

    # Defense in depth: never trust ANY provider's selected_action, even
    # the deterministic one's, without re-confirming it against the set we
    # ourselves just computed.
    if decision_result.selected_action is not None and decision_result.selected_action not in context.action_types():
        decision_result = ProviderDecision(
            selected_action=None,
            reasoning_summary="Provider selected an action outside the currently allowed set — rejected "
            f"and treated as no-action pending human review. Original reasoning: {decision_result.reasoning_summary}",
            confidence=decision_result.confidence,
            requires_human_review=True,
            risk_flags=[*decision_result.risk_flags, "invalid_provider_selection"],
        )

    deterministic_flags = compute_deterministic_risk_flags(
        context,
        high_value_threshold_cents=settings.human_review_amount_threshold_cents,
        confidence_floor=settings.human_review_confidence_floor,
        repeated_failure_threshold=settings.human_review_repeated_failure_threshold,
    )
    combined_flags = sorted(set(decision_result.risk_flags) | set(deterministic_flags))
    requires_review = decision_result.requires_human_review or bool(deterministic_flags)
    if decision_result.selected_action is None:
        requires_review = True  # never auto-approve "nothing to do" silently

    status = DecisionStatus.HUMAN_REVIEW if requires_review else DecisionStatus.AUTO_APPROVED

    latest_prediction = case_query.latest_ml_prediction(db, case.id)
    latest_attempt = case_query.latest_diagnosed_attempt(db, case.id)
    latest_policy_row = (
        db.query(PolicyDecision)
        .filter(PolicyDecision.case_id == case.id)
        .order_by(PolicyDecision.evaluated_at.desc())
        .first()
    )

    row = AgentDecision(
        case_id=case.id,
        payment_attempt_id=latest_attempt.id if latest_attempt else None,
        ml_prediction_id=latest_prediction.id if latest_prediction else None,
        policy_decision_id=latest_policy_row.id if latest_policy_row else None,
        agent_mode=agent_mode,
        provider_name=provider_name,
        policy_version=context.policy_version,
        available_actions=[
            {
                "action_type": a.action_type,
                "reason_code": a.reason_code,
                "message": a.message,
                "expected_value_cents": a.expected_value_cents,
            }
            for a in context.available_actions
        ],
        expected_values_cents={a.action_type: a.expected_value_cents for a in context.available_actions},
        recovery_probability=context.recovery_probability,
        selected_action=ActionType(decision_result.selected_action) if decision_result.selected_action else None,
        reasoning_summary=decision_result.reasoning_summary,
        confidence=decision_result.confidence,
        risk_flags=combined_flags,
        requires_human_review=requires_review,
        status=status,
    )
    db.add(row)
    db.flush()

    for i, (name, inp, out) in enumerate(tool_calls, start=1):
        db.add(
            AgentToolCall(agent_decision_id=row.id, sequence=i, tool_name=name, input_summary=inp, output_summary=out)
        )
    db.flush()

    engine_label = "Agentic AI Decision Engine" if agent_mode == AgentMode.LLM else "Deterministic Decision Engine"
    outcome_label = f"selected {row.selected_action.value}" if row.selected_action else "found no safe action"
    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.AGENT_DECIDED,
        summary=f"[{engine_label}] {outcome_label}" + (" — human review required." if requires_review else "."),
        details={
            "agent_decision_id": row.id,
            "agent_mode": agent_mode.value,
            "provider_name": provider_name,
            "selected_action": row.selected_action.value if row.selected_action else None,
            "confidence": row.confidence,
            "risk_flags": combined_flags,
        },
        payment_attempt_id=latest_attempt.id if latest_attempt else None,
    )
    db.commit()
    db.refresh(row)
    return row


def execute(
    db: Session,
    *,
    agent_decision: AgentDecision,
    gateway: PaymentGatewayPort,
    client_request_id: str | None = None,
) -> tuple[AgentDecision, Action | None, ActionOutcome | None, PaymentAttempt | None, bool]:
    if agent_decision.status == DecisionStatus.HUMAN_REVIEW:
        raise AgentDecisionNotExecutable(
            "human_review_required", "This decision requires human approval before it can execute."
        )
    if agent_decision.status in (DecisionStatus.REJECTED, DecisionStatus.ESCALATED):
        raise AgentDecisionNotExecutable("already_finalized", f"This decision is already {agent_decision.status.value}.")
    # Deliberately NOT blocking status == EXECUTED here: a repeat call with
    # the same client_request_id must dedupe, not error — that's handled
    # below by action_service.request_action's own idempotency, the exact
    # same mechanism a human clicking "retry" twice goes through. A repeat
    # call with no/different client_request_id is re-evaluated against
    # current policy (cooldown, retry cap, case-terminal) exactly as any
    # other action request would be.

    case = db.get(Case, agent_decision.case_id)
    if case is None:
        raise AgentDecisionNotExecutable("case_not_found", f"Case {agent_decision.case_id} not found.")

    if agent_decision.selected_action is None:
        agent_decision.status = DecisionStatus.ESCALATED
        db.flush()
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.CASE_ESCALATED,
            summary="Agent decision selected no action — case requires human escalation.",
            details={"agent_decision_id": agent_decision.id},
        )
        db.commit()
        db.refresh(agent_decision)
        return agent_decision, None, None, None, False

    try:
        action, outcome, resulting_attempt, deduplicated = action_service.request_action(
            db,
            case=case,
            action_type=agent_decision.selected_action,
            gateway=gateway,
            client_request_id=client_request_id,
        )
    except ActionNotEligible as exc:
        agent_decision.status = DecisionStatus.REJECTED
        agent_decision.review_note = f"Execution refused on server re-validation: {exc.reason_code} — {exc.message}"
        db.flush()
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.ACTION_REJECTED,
            summary=f"Agent-selected action rejected on server re-validation: {exc.reason_code}.",
            details={"agent_decision_id": agent_decision.id, "reason_code": exc.reason_code},
        )
        db.commit()
        db.refresh(agent_decision)
        raise

    agent_decision.status = DecisionStatus.EXECUTED
    agent_decision.executed_action_id = action.id
    db.flush()
    db.commit()
    db.refresh(agent_decision)
    db.refresh(case)
    return agent_decision, action, outcome, resulting_attempt, deduplicated


def approve_decision(
    db: Session,
    *,
    agent_decision: AgentDecision,
    reviewed_by: str,
    note: str | None,
    gateway: PaymentGatewayPort,
    client_request_id: str | None = None,
) -> tuple[AgentDecision, Action | None, ActionOutcome | None, PaymentAttempt | None, bool]:
    if agent_decision.status != DecisionStatus.HUMAN_REVIEW:
        raise AgentDecisionNotExecutable(
            "not_pending_review", f"This decision is not pending review (status={agent_decision.status.value})."
        )
    agent_decision.reviewed_by = reviewed_by
    agent_decision.reviewed_at = datetime.now(timezone.utc)
    agent_decision.review_note = note
    agent_decision.status = DecisionStatus.AUTO_APPROVED
    db.flush()
    audit_service.write_event(
        db,
        case_id=agent_decision.case_id,
        event_type=CaseEventType.AGENT_DECISION_REVIEWED,
        summary=f"Decision approved by {reviewed_by}." + (f" {note}" if note else ""),
        details={"agent_decision_id": agent_decision.id, "outcome": "approved", "note": note},
    )
    db.commit()
    db.refresh(agent_decision)
    return execute(db, agent_decision=agent_decision, gateway=gateway, client_request_id=client_request_id)


def reject_decision(db: Session, *, agent_decision: AgentDecision, reviewed_by: str, note: str | None) -> AgentDecision:
    if agent_decision.status != DecisionStatus.HUMAN_REVIEW:
        raise AgentDecisionNotExecutable(
            "not_pending_review", f"This decision is not pending review (status={agent_decision.status.value})."
        )
    agent_decision.status = DecisionStatus.REJECTED
    agent_decision.reviewed_by = reviewed_by
    agent_decision.reviewed_at = datetime.now(timezone.utc)
    agent_decision.review_note = note
    db.flush()
    audit_service.write_event(
        db,
        case_id=agent_decision.case_id,
        event_type=CaseEventType.AGENT_DECISION_REVIEWED,
        summary=f"Decision rejected by {reviewed_by}." + (f" {note}" if note else ""),
        details={"agent_decision_id": agent_decision.id, "outcome": "rejected", "note": note},
    )
    db.commit()
    db.refresh(agent_decision)
    return agent_decision
