import pytest

from app.agent import tools
from app.agent.types import ToolContext
from app.domain.enums import AttemptSource, CaseStatus, DeclineCode
from app.models.cases import Case
from app.models.core import Invoice
from app.services import audit_service, ingestion_service


@pytest.fixture()
def case_with_failure(session_factory, seeded_invoice):
    db = session_factory()
    try:
        invoice = db.get(Invoice, seeded_invoice["invoice_id"])
        result = ingestion_service.record_payment_attempt(
            db,
            invoice=invoice,
            payment_method_id=seeded_invoice["payment_method_id"],
            amount_cents=4900,
            currency="usd",
            decline_code=DeclineCode.CARD_DECLINED,
            source=AttemptSource.EXTERNAL,
        )
        case_id = result.case.id
    finally:
        db.close()

    db2 = session_factory()
    try:
        yield db2, db2.get(Case, case_id)
    finally:
        db2.close()


def test_get_transaction_returns_current_attempt(case_with_failure):
    db, case = case_with_failure
    result = tools.get_transaction(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.decline_code == "card_declined"
    assert result.amount_cents == 4900


def test_get_customer_history_defaults_to_neutral_prior(case_with_failure):
    db, case = case_with_failure
    result = tools.get_customer_history(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.prior_recovery_rate == 0.5
    assert result.prior_successful_attempts == 0


def test_analyze_payment_failure_matches_taxonomy(case_with_failure):
    db, case = case_with_failure
    result = tools.analyze_payment_failure(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.decline_class == "soft"
    assert "retry_payment" in result.relevant_actions


def test_calculate_recovery_probability_unavailable_without_a_model(case_with_failure):
    db, case = case_with_failure
    result = tools.calculate_recovery_probability(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.is_available is False
    assert result.recovery_probability is None


def test_check_retry_eligibility_allowed_for_a_fresh_soft_decline(case_with_failure):
    db, case = case_with_failure
    result = tools.check_retry_eligibility(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.retry_allowed is True
    assert result.reason_code == "eligible"


def test_get_recovery_policy_lists_all_three_action_types(case_with_failure):
    db, case = case_with_failure
    result = tools.get_recovery_policy(ToolContext(db=db, case=case), tools.EmptyInput())
    assert {e.action_type for e in result.eligibilities} == {"retry_payment", "request_method_update", "escalate"}


def test_get_case_state_reflects_open_case(case_with_failure):
    db, case = case_with_failure
    result = tools.get_case_state(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.status == "open"
    assert result.prior_actions_count == 0


def test_calculate_expected_recovery_value_uses_zero_probability_without_a_model(case_with_failure):
    db, case = case_with_failure
    result = tools.calculate_expected_recovery_value(ToolContext(db=db, case=case), tools.EmptyInput())
    assert result.expected_values_cents["retry_payment"] == -25  # no model active -> probability treated as 0.0


def test_create_recovery_message_logs_an_event(case_with_failure):
    db, case = case_with_failure
    result = tools.create_recovery_message(ToolContext(db=db, case=case), tools.RecoveryMessageInput(channel="sms"))
    assert result.logged is True
    assert result.channel == "sms"
    events = audit_service.list_events(db, case.id)
    assert any((e.details or {}).get("channel") == "sms" for e in events)


def test_record_audit_event_logs_the_note(case_with_failure):
    db, case = case_with_failure
    result = tools.record_audit_event(ToolContext(db=db, case=case), tools.AuditNoteInput(note="agent thinking out loud"))
    assert result.recorded is True
    events = audit_service.list_events(db, case.id)
    assert any(e.summary == "agent thinking out loud" for e in events)


def test_call_tool_dispatches_by_name(case_with_failure):
    db, case = case_with_failure
    result = tools.call_tool(ToolContext(db=db, case=case), "get_case_state", {})
    assert result.status == "open"


def test_call_tool_rejects_unknown_tool_name(case_with_failure):
    db, case = case_with_failure
    with pytest.raises(tools.ToolError):
        tools.call_tool(ToolContext(db=db, case=case), "delete_everything", {})


def test_call_tool_rejects_invalid_input_shape(case_with_failure):
    db, case = case_with_failure
    with pytest.raises(tools.ToolError):
        tools.call_tool(ToolContext(db=db, case=case), "create_recovery_message", {"channel": 12345})


def test_get_transaction_raises_for_a_case_with_no_diagnosed_attempt(session_factory, seeded_invoice):
    db = session_factory()
    try:
        case = Case(
            invoice_id=seeded_invoice["invoice_id"],
            customer_id=seeded_invoice["customer_id"],
            status=CaseStatus.OPEN,
            amount_at_risk_cents=4900,
            currency="usd",
        )
        db.add(case)
        db.commit()
        with pytest.raises(tools.ToolError):
            tools.get_transaction(ToolContext(db=db, case=case), tools.EmptyInput())
    finally:
        db.close()
