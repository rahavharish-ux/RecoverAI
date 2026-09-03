from datetime import datetime, timezone

from app.agent.risk import compute_deterministic_risk_flags
from app.agent.types import AvailableAction, DecisionContext

DEFAULTS = dict(high_value_threshold_cents=10000, confidence_floor=0.40, repeated_failure_threshold=2)


def make_context(**overrides) -> DecisionContext:
    defaults = dict(
        case_id=1,
        case_status="open",
        amount_at_risk_cents=4900,
        currency="usd",
        decline_code="card_declined",
        decline_class="soft",
        diagnosis_explanation="test",
        recovery_probability=0.7,
        confidence_band="high",
        model_version="v1",
        top_contributions=[],
        customer_plan_tier="standard",
        customer_tenure_days=200.0,
        customer_prior_recovery_rate=0.6,
        prior_failed_attempts_on_case=0,
        executed_retry_count=0,
        policy_version="policy-v1",
        available_actions=[AvailableAction("retry_payment", "eligible", "ok", 3400)],
        generated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return DecisionContext(**defaults)


def test_no_flags_for_a_clean_low_risk_case():
    flags = compute_deterministic_risk_flags(make_context(), **DEFAULTS)
    assert flags == []


def test_fraud_class_always_flagged():
    flags = compute_deterministic_risk_flags(make_context(decline_class="fraud"), **DEFAULTS)
    assert "fraud_signal" in flags


def test_high_value_transaction_flagged_at_or_above_threshold():
    flags = compute_deterministic_risk_flags(make_context(amount_at_risk_cents=10000), **DEFAULTS)
    assert "high_value_transaction" in flags


def test_amount_just_below_threshold_not_flagged():
    flags = compute_deterministic_risk_flags(make_context(amount_at_risk_cents=9999), **DEFAULTS)
    assert "high_value_transaction" not in flags


def test_low_model_confidence_flagged_below_floor():
    flags = compute_deterministic_risk_flags(make_context(recovery_probability=0.10), **DEFAULTS)
    assert "low_model_confidence" in flags


def test_no_probability_available_is_not_treated_as_low_confidence():
    flags = compute_deterministic_risk_flags(make_context(recovery_probability=None), **DEFAULTS)
    assert "low_model_confidence" not in flags


def test_repeated_failures_flagged_at_threshold():
    flags = compute_deterministic_risk_flags(make_context(prior_failed_attempts_on_case=2), **DEFAULTS)
    assert "repeated_recovery_failures" in flags


def test_no_allowed_actions_flagged():
    flags = compute_deterministic_risk_flags(make_context(available_actions=[]), **DEFAULTS)
    assert "no_allowed_actions" in flags


def test_conflicting_signals_flagged_when_top_two_expected_values_are_close():
    context = make_context(
        available_actions=[
            AvailableAction("retry_payment", "eligible", "ok", 1000),
            AvailableAction("request_method_update", "eligible", "ok", 950),
        ]
    )
    flags = compute_deterministic_risk_flags(context, **DEFAULTS)
    assert "conflicting_signals" in flags


def test_no_conflict_flagged_when_one_action_clearly_dominates():
    context = make_context(
        available_actions=[
            AvailableAction("retry_payment", "eligible", "ok", 3400),
            AvailableAction("escalate", "eligible", "ok", -500),
        ]
    )
    flags = compute_deterministic_risk_flags(context, **DEFAULTS)
    assert "conflicting_signals" not in flags


def test_multiple_conditions_all_flagged_simultaneously():
    context = make_context(decline_class="fraud", amount_at_risk_cents=50000, recovery_probability=0.01)
    flags = compute_deterministic_risk_flags(context, **DEFAULTS)
    assert set(flags) >= {"fraud_signal", "high_value_transaction", "low_model_confidence"}
