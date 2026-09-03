"""Deterministic risk-flag computation, applied to EVERY decision
regardless of which provider produced it. A provider's own
`requires_human_review` can only ever be strengthened (OR'd) by this here
— never weakened. An agent's own judgment that a case is safe is never,
by itself, sufficient authorization for a risky one (see
app/services/agent_service.py)."""

from app.agent.types import DecisionContext


def compute_deterministic_risk_flags(
    context: DecisionContext,
    *,
    high_value_threshold_cents: int,
    confidence_floor: float,
    repeated_failure_threshold: int,
) -> list[str]:
    flags: list[str] = []

    if context.decline_class == "fraud":
        flags.append("fraud_signal")
    if context.amount_at_risk_cents >= high_value_threshold_cents:
        flags.append("high_value_transaction")
    if context.recovery_probability is not None and context.recovery_probability < confidence_floor:
        flags.append("low_model_confidence")
    if context.prior_failed_attempts_on_case >= repeated_failure_threshold:
        flags.append("repeated_recovery_failures")
    if not context.available_actions:
        flags.append("no_allowed_actions")

    values = sorted((a.expected_value_cents for a in context.available_actions), reverse=True)
    if len(values) >= 2 and values[0] > 0 and (values[0] - values[1]) < max(1, 0.1 * values[0]):
        flags.append("conflicting_signals")

    return flags
