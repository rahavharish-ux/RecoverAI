from datetime import datetime, timezone

from app.agent.deterministic_provider import DeterministicDecisionEngine
from app.agent.types import AvailableAction, DecisionContext

ENGINE = DeterministicDecisionEngine()


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
        available_actions=[
            AvailableAction("retry_payment", "eligible", "ok", 3400),
            AvailableAction("escalate", "eligible", "ok", -500),
        ],
        generated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return DecisionContext(**defaults)


def test_selects_the_highest_expected_value_action():
    decision = ENGINE.generate_decision(make_context(), tool_context=None)
    assert decision.selected_action == "retry_payment"


def test_selects_escalate_when_it_is_the_only_positive_or_only_option():
    context = make_context(available_actions=[AvailableAction("escalate", "eligible", "ok", -500)])
    decision = ENGINE.generate_decision(context, tool_context=None)
    assert decision.selected_action == "escalate"


def test_no_action_when_nothing_is_allowed():
    context = make_context(available_actions=[])
    decision = ENGINE.generate_decision(context, tool_context=None)
    assert decision.selected_action is None
    assert decision.requires_human_review is True
    assert "no_allowed_actions" in decision.risk_flags


def test_confidence_reflects_recovery_probability_when_available():
    decision = ENGINE.generate_decision(make_context(recovery_probability=0.42), tool_context=None)
    assert decision.confidence == 0.42


def test_confidence_defaults_when_no_probability_available():
    decision = ENGINE.generate_decision(make_context(recovery_probability=None), tool_context=None)
    assert decision.confidence == 0.5


def test_reasoning_summary_mentions_the_decline_and_selected_action():
    decision = ENGINE.generate_decision(make_context(), tool_context=None)
    assert "card_declined" in decision.reasoning_summary
    assert "retry_payment" in decision.reasoning_summary


def test_never_sets_requires_human_review_itself():
    """The engine's own opinion is always False — risk flags are OR'd in
    by the caller (app/services/agent_service.py), never decided here."""
    decision = ENGINE.generate_decision(make_context(), tool_context=None)
    assert decision.requires_human_review is False


def test_provider_identity_is_clearly_labeled_deterministic():
    assert ENGINE.mode == "deterministic"
    assert "deterministic" in ENGINE.name
