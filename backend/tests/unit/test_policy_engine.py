from datetime import datetime, timedelta, timezone

import pytest

from app.domain.decline_taxonomy import Diagnosis, diagnose
from app.domain.enums import ActionType, CaseStatus, DeclineClass, DeclineCode, PolicyReasonCode
from app.domain.policy import PolicyInput, PolicySettings, evaluate

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def make_input(**overrides) -> PolicyInput:
    defaults = dict(
        case_status=CaseStatus.OPEN,
        diagnosis=diagnose(DeclineCode.CARD_DECLINED),
        executed_retry_count=0,
        last_retry_at=None,
        now=NOW,
        has_in_flight_action={},
        settings=PolicySettings(),
    )
    defaults.update(overrides)
    return PolicyInput(**defaults)


def elig(result, action_type):
    e = result.eligibility_for(action_type)
    assert e is not None
    return e


# --- Rule 1: kill switch --------------------------------------------------


def test_kill_switch_blocks_every_action_type():
    result = evaluate(make_input(settings=PolicySettings(automated_actions_enabled=False)))
    assert result.allowed_actions == ()
    assert all(e.reason_code == PolicyReasonCode.AUTOMATION_PAUSED for e in result.eligibilities)


# --- Rule 2: terminal case -------------------------------------------------


@pytest.mark.parametrize("status", [CaseStatus.RESOLVED, CaseStatus.ESCALATED])
def test_terminal_case_blocks_every_action_type(status):
    result = evaluate(make_input(case_status=status))
    assert result.allowed_actions == ()
    assert all(e.reason_code == PolicyReasonCode.CASE_TERMINAL for e in result.eligibilities)


# --- Rule 3: in-flight duplicate -------------------------------------------


def test_in_flight_action_blocks_a_duplicate_of_the_same_type():
    result = evaluate(make_input(has_in_flight_action={ActionType.RETRY_PAYMENT: True}))
    e = elig(result, ActionType.RETRY_PAYMENT)
    assert not e.allowed
    assert e.reason_code == PolicyReasonCode.ACTION_IN_FLIGHT


def test_in_flight_only_blocks_its_own_action_type():
    result = evaluate(make_input(has_in_flight_action={ActionType.RETRY_PAYMENT: True}))
    e = elig(result, ActionType.ESCALATE)
    assert e.allowed


# --- Rule 4: fraud gate -----------------------------------------------------


def test_fraud_signal_allows_only_escalate():
    result = evaluate(make_input(diagnosis=diagnose(DeclineCode.FRAUD_SUSPECTED)))
    assert result.allowed_actions == (ActionType.ESCALATE,)


def test_fraud_signal_reason_code_on_retry():
    result = evaluate(make_input(diagnosis=diagnose(DeclineCode.FRAUD_SUSPECTED)))
    e = elig(result, ActionType.RETRY_PAYMENT)
    assert not e.allowed
    assert e.reason_code == PolicyReasonCode.FRAUD_SIGNAL


def test_hard_decline_gate_is_independent_defense_even_if_the_relevance_table_were_wrong():
    """Every current HARD-class decline code already excludes RETRY_PAYMENT
    from its relevance table (rule 5), so rule 6 is normally unreachable —
    it exists as a second, independent gate in case a future taxonomy entry
    is mis-tabled. Prove it actually holds on its own by feeding it a
    deliberately "wrong" diagnosis that a taxonomy bug might produce."""
    bad_diagnosis = Diagnosis(
        decline_code=DeclineCode.DO_NOT_HONOR,
        decline_class=DeclineClass.HARD,
        relevant_actions=frozenset({ActionType.RETRY_PAYMENT, ActionType.ESCALATE}),
        explanation="hypothetically mis-tabled for this test",
    )
    result = evaluate(make_input(diagnosis=bad_diagnosis))
    e = elig(result, ActionType.RETRY_PAYMENT)
    assert not e.allowed
    assert e.reason_code == PolicyReasonCode.HARD_DECLINE


# --- Rule 5: decline-code relevance -----------------------------------------


def test_insufficient_funds_never_offers_method_update():
    result = evaluate(make_input(diagnosis=diagnose(DeclineCode.INSUFFICIENT_FUNDS)))
    e = elig(result, ActionType.REQUEST_METHOD_UPDATE)
    assert not e.allowed
    assert e.reason_code == PolicyReasonCode.NOT_APPLICABLE_TO_DECLINE_REASON


def test_do_not_honor_never_offers_retry_or_method_update():
    result = evaluate(make_input(diagnosis=diagnose(DeclineCode.DO_NOT_HONOR)))
    assert not elig(result, ActionType.RETRY_PAYMENT).allowed
    assert not elig(result, ActionType.REQUEST_METHOD_UPDATE).allowed
    assert elig(result, ActionType.ESCALATE).allowed


# --- Rule 6: hard decline gate ----------------------------------------------


def test_hard_decline_retry_is_always_prohibited():
    result = evaluate(make_input(diagnosis=diagnose(DeclineCode.INVALID_METHOD)))
    assert not elig(result, ActionType.RETRY_PAYMENT).allowed


# --- Rules 7 & 8: retry cap and cooldown ------------------------------------


def test_retry_below_cap_and_outside_cooldown_is_eligible():
    result = evaluate(make_input(executed_retry_count=1, last_retry_at=NOW - timedelta(hours=48)))
    assert elig(result, ActionType.RETRY_PAYMENT).allowed


def test_retry_cap_reached_blocks_further_retries():
    result = evaluate(make_input(executed_retry_count=3, settings=PolicySettings(max_retry_attempts=3)))
    e = elig(result, ActionType.RETRY_PAYMENT)
    assert not e.allowed
    assert e.reason_code == PolicyReasonCode.RETRY_LIMIT_REACHED


def test_retry_cap_uses_configured_threshold_not_a_hardcoded_one():
    result = evaluate(make_input(executed_retry_count=1, settings=PolicySettings(max_retry_attempts=1)))
    assert not elig(result, ActionType.RETRY_PAYMENT).allowed


def test_cooldown_blocks_a_retry_requested_too_soon():
    result = evaluate(
        make_input(last_retry_at=NOW - timedelta(hours=1), settings=PolicySettings(retry_cooldown_hours=24))
    )
    e = elig(result, ActionType.RETRY_PAYMENT)
    assert not e.allowed
    assert e.reason_code == PolicyReasonCode.COOLDOWN_ACTIVE
    assert e.retry_after == NOW - timedelta(hours=1) + timedelta(hours=24)


def test_cooldown_clears_once_the_window_has_passed():
    result = evaluate(
        make_input(last_retry_at=NOW - timedelta(hours=25), settings=PolicySettings(retry_cooldown_hours=24))
    )
    assert elig(result, ActionType.RETRY_PAYMENT).allowed


def test_no_prior_retry_has_no_cooldown_to_wait_out():
    result = evaluate(make_input(last_retry_at=None))
    assert elig(result, ActionType.RETRY_PAYMENT).allowed


# --- Positive path + full coverage ------------------------------------------


def test_eligible_action_carries_the_eligible_reason_code():
    result = evaluate(make_input())
    e = elig(result, ActionType.RETRY_PAYMENT)
    assert e.allowed
    assert e.reason_code == PolicyReasonCode.ELIGIBLE


@pytest.mark.parametrize("code", list(DeclineCode))
def test_every_decline_code_produces_a_complete_eligibility_table(code):
    result = evaluate(make_input(diagnosis=diagnose(code)))
    assert {e.action_type for e in result.eligibilities} == set(ActionType)
    for e in result.eligibilities:
        assert isinstance(e.allowed, bool)
        assert e.message
