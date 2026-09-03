"""Tests the aggregation math directly against service calls (not the API
layer) so each figure's provenance is unambiguous: every assertion here
can be traced to specific cases/attempts/decisions this test itself
created."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.enums import ActionType, AgentMode, AttemptSource, DeclineCode
from app.integrations.payment_gateway import GatewayResult, PaymentGatewayPort
from app.models.agent import AgentDecision
from app.models.core import Customer, Invoice, PaymentMethod, Subscription
from app.services import action_service, agent_service, dashboard_service, ingestion_service


class _AlwaysSucceed(PaymentGatewayPort):
    def retry_charge(self, *, decline_code, amount_cents, currency):
        return GatewayResult(succeeded=True, decline_code=None)


class _AlwaysFail(PaymentGatewayPort):
    def retry_charge(self, *, decline_code, amount_cents, currency):
        return GatewayResult(succeeded=False, decline_code=decline_code)


def _open_case(db, seeded_invoice, decline_code=DeclineCode.CARD_DECLINED, amount_cents=4900):
    """NOTE: the case's amount_at_risk_cents always ends up equal to the
    INVOICE's amount_cents (fixed at 4900 by the seeded_invoice fixture) —
    the ingest payload's own amount_cents does not drive it. See
    ingestion_service._get_or_create_open_case."""
    invoice = db.get(Invoice, seeded_invoice["invoice_id"])
    result = ingestion_service.record_payment_attempt(
        db,
        invoice=invoice,
        payment_method_id=seeded_invoice["payment_method_id"],
        amount_cents=amount_cents,
        currency="usd",
        decline_code=decline_code,
        source=AttemptSource.EXTERNAL,
    )
    return result.case


def _second_invoice(db, amount_cents: int) -> dict:
    """A distinct customer/invoice, so a second case can be opened
    concurrently with one still open on seeded_invoice's invoice — reusing
    the same invoice would just reuse the same still-open case."""
    customer = Customer(name="Second Customer", email="second@example.com", plan_tier="standard")
    db.add(customer)
    db.flush()
    method = PaymentMethod(customer_id=customer.id, brand="visa", last4="1111", exp_month=1, exp_year=2031)
    db.add(method)
    db.flush()
    subscription = Subscription(customer_id=customer.id, plan_tier="standard", status="active")
    db.add(subscription)
    db.flush()
    invoice = Invoice(
        subscription_id=subscription.id,
        customer_id=customer.id,
        amount_cents=amount_cents,
        currency="usd",
        due_date=datetime.now(timezone.utc) + timedelta(days=1),
        status="open",
    )
    db.add(invoice)
    db.commit()
    return {"invoice_id": invoice.id, "payment_method_id": method.id, "customer_id": customer.id}


def test_summary_is_all_zero_on_an_empty_database(session_factory):
    db = session_factory()
    try:
        summary = dashboard_service.get_summary(db)
        assert summary.revenue_at_risk_cents == 0
        assert summary.recovered_revenue_cents == 0
        assert summary.recovery_rate is None
        assert summary.active_recovery_cases == 0
        assert summary.failed_payments == 0
        assert summary.human_escalations == 0
    finally:
        db.close()


def test_summary_revenue_at_risk_reflects_open_cases_only(session_factory, seeded_invoice):
    db = session_factory()
    try:
        _open_case(db, seeded_invoice, amount_cents=4900)
        summary = dashboard_service.get_summary(db)
        assert summary.revenue_at_risk_cents == 4900
        assert summary.active_recovery_cases == 1
        assert summary.failed_payments == 1
    finally:
        db.close()


def test_summary_recovery_rate_counts_resolved_vs_escalated(session_factory, seeded_invoice):
    db = session_factory()
    try:
        case1 = _open_case(db, seeded_invoice, decline_code=DeclineCode.PROCESSOR_ERROR)
        action_service.request_action(
            db, case=case1, action_type=ActionType.RETRY_PAYMENT, gateway=_AlwaysSucceed(), client_request_id="a"
        )
        case2 = _open_case(db, seeded_invoice, decline_code=DeclineCode.FRAUD_SUSPECTED)
        action_service.request_action(
            db, case=case2, action_type=ActionType.ESCALATE, gateway=_AlwaysFail(), client_request_id="b"
        )

        summary = dashboard_service.get_summary(db)
        assert summary.recovery_rate == pytest.approx(0.5)
        assert summary.recovered_revenue_cents == 4900
    finally:
        db.close()


def test_funnel_counts_decrease_monotonically_and_recovered_is_a_subset(session_factory, seeded_invoice):
    db = session_factory()
    try:
        case = _open_case(db, seeded_invoice, decline_code=DeclineCode.PROCESSOR_ERROR)
        action_service.request_action(
            db, case=case, action_type=ActionType.RETRY_PAYMENT, gateway=_AlwaysSucceed(), client_request_id="a"
        )
        stages = {s.stage: s.case_count for s in dashboard_service.get_funnel(db)}
        assert stages["failed_payment"] == 1
        assert stages["diagnosed"] == 1
        assert stages["policy_eligible"] == 1
        assert stages["recovery_action"] == 1
        assert stages["recovered"] == 1
    finally:
        db.close()


def test_funnel_fraud_case_never_reaches_policy_eligible(session_factory, seeded_invoice):
    """Fraud only ever allows escalate — not a self-service recovery path
    — so it must not count toward policy_eligible."""
    db = session_factory()
    try:
        _open_case(db, seeded_invoice, decline_code=DeclineCode.FRAUD_SUSPECTED)
        stages = {s.stage: s.case_count for s in dashboard_service.get_funnel(db)}
        assert stages["diagnosed"] == 1
        assert stages["policy_eligible"] == 0
    finally:
        db.close()


def test_failure_categories_groups_by_originating_decline_code(session_factory, seeded_invoice):
    db = session_factory()
    try:
        _open_case(db, seeded_invoice, decline_code=DeclineCode.CARD_DECLINED)
        categories = dashboard_service.get_failure_categories(db)
        assert len(categories) == 1
        assert categories[0].decline_code == "card_declined"
        assert categories[0].case_count == 1
        assert categories[0].amount_involved_cents == 4900  # the seeded invoice's amount
        assert categories[0].retry_eligible is True
    finally:
        db.close()


def test_failure_categories_expired_card_is_not_retry_eligible(session_factory, seeded_invoice):
    db = session_factory()
    try:
        _open_case(db, seeded_invoice, decline_code=DeclineCode.EXPIRED_CARD)
        categories = dashboard_service.get_failure_categories(db)
        assert categories[0].retry_eligible is False
    finally:
        db.close()


def test_recent_decisions_labels_deterministic_engine_correctly(session_factory, seeded_invoice):
    db = session_factory()
    try:
        case = _open_case(db, seeded_invoice, decline_code=DeclineCode.PROCESSOR_ERROR)
        agent_service.decide(db, case=case)
        decisions = dashboard_service.get_recent_decisions(db)
        assert len(decisions) == 1
        assert decisions[0].agent_mode == "deterministic"
        assert decisions[0].mode_label == "Deterministic Decision Engine"
    finally:
        db.close()


def test_recent_decisions_labels_llm_mode_correctly_and_never_as_deterministic(session_factory, seeded_invoice):
    db = session_factory()
    try:
        case = _open_case(db, seeded_invoice, decline_code=DeclineCode.PROCESSOR_ERROR)
        agent_service.decide(db, case=case)
        row = db.query(AgentDecision).filter(AgentDecision.case_id == case.id).first()
        row.agent_mode = AgentMode.LLM
        row.provider_name = "anthropic-claude"
        db.commit()

        decisions = dashboard_service.get_recent_decisions(db)
        assert decisions[0].agent_mode == "llm"
        assert decisions[0].mode_label == "Agentic AI Decision Engine"
        assert decisions[0].mode_label != "Deterministic Decision Engine"
    finally:
        db.close()


def test_priority_cases_only_includes_open_cases_ranked_by_amount(session_factory, seeded_invoice):
    db = session_factory()
    try:
        small_invoice = _second_invoice(db, amount_cents=500)
        large_invoice = _second_invoice(db, amount_cents=9000)
        small = _open_case(db, small_invoice, decline_code=DeclineCode.CARD_DECLINED)
        large = _open_case(db, large_invoice, decline_code=DeclineCode.PROCESSOR_ERROR)
        # this one resolves immediately and must be excluded
        resolved_case = _open_case(db, seeded_invoice, decline_code=DeclineCode.INSUFFICIENT_FUNDS)
        action_service.request_action(
            db, case=resolved_case, action_type=ActionType.RETRY_PAYMENT, gateway=_AlwaysSucceed(), client_request_id="r"
        )

        priority = dashboard_service.get_priority_cases(db)
        case_ids = [p.case_id for p in priority]
        assert resolved_case.id not in case_ids
        assert case_ids.index(large.id) < case_ids.index(small.id)
    finally:
        db.close()


def test_economics_action_cost_reflects_configured_costs(session_factory, seeded_invoice):
    db = session_factory()
    try:
        case = _open_case(db, seeded_invoice, decline_code=DeclineCode.PROCESSOR_ERROR)
        action_service.request_action(
            db, case=case, action_type=ActionType.RETRY_PAYMENT, gateway=_AlwaysSucceed(), client_request_id="a"
        )
        economics = dashboard_service.get_economics(db)
        assert economics.action_cost_cents == 25  # default retry_payment cost from Settings.action_costs_cents
        assert economics.recovered_revenue_cents == 4900
        assert economics.net_recovery_value_cents == 4900 - 25
        assert economics.recovery_attempts == 1
        assert economics.successful_recoveries == 1
    finally:
        db.close()


def test_economics_potential_recoverable_uses_the_latest_prediction(session_factory, seeded_invoice, stub_active_model):
    db = session_factory()
    try:
        _open_case(db, seeded_invoice, decline_code=DeclineCode.CARD_DECLINED)
        economics = dashboard_service.get_economics(db)
        # StubPipeline (see conftest.py) returns 0.55 for a retry-eligible, non-fraud case
        assert economics.potential_recoverable_cents == round(0.55 * 4900)
    finally:
        db.close()
