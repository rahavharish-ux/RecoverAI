import pytest

from app.domain.decline_taxonomy import diagnose
from app.domain.enums import ActionType, DeclineClass, DeclineCode

EXPECTED = {
    DeclineCode.INSUFFICIENT_FUNDS: (DeclineClass.SOFT, {ActionType.RETRY_PAYMENT, ActionType.ESCALATE}),
    DeclineCode.CARD_DECLINED: (
        DeclineClass.SOFT,
        {ActionType.RETRY_PAYMENT, ActionType.REQUEST_METHOD_UPDATE, ActionType.ESCALATE},
    ),
    DeclineCode.PROCESSOR_ERROR: (DeclineClass.SOFT, {ActionType.RETRY_PAYMENT, ActionType.ESCALATE}),
    DeclineCode.EXPIRED_CARD: (DeclineClass.SOFT, {ActionType.REQUEST_METHOD_UPDATE, ActionType.ESCALATE}),
    DeclineCode.INVALID_METHOD: (DeclineClass.HARD, {ActionType.REQUEST_METHOD_UPDATE, ActionType.ESCALATE}),
    DeclineCode.DO_NOT_HONOR: (DeclineClass.HARD, {ActionType.ESCALATE}),
    DeclineCode.FRAUD_SUSPECTED: (DeclineClass.FRAUD, {ActionType.ESCALATE}),
}


@pytest.mark.parametrize("code", list(DeclineCode))
def test_diagnose_matches_the_expected_profile(code):
    expected_class, expected_relevant = EXPECTED[code]
    diagnosis = diagnose(code)
    assert diagnosis.decline_class == expected_class
    assert diagnosis.relevant_actions == frozenset(expected_relevant)
    assert diagnosis.explanation.strip() != ""


def test_expired_card_can_never_be_retried():
    assert ActionType.RETRY_PAYMENT not in diagnose(DeclineCode.EXPIRED_CARD).relevant_actions


def test_fraud_signal_only_ever_escalates():
    assert diagnose(DeclineCode.FRAUD_SUSPECTED).relevant_actions == frozenset({ActionType.ESCALATE})


def test_every_enum_member_has_a_profile():
    for code in DeclineCode:
        diagnose(code)  # must not raise KeyError
