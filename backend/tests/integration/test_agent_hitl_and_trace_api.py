"""Human-in-the-loop transitions, the persisted agent trace, the per-case
decision cap, and the audit trail's completeness."""


def _ingest_failure(client, seeded_invoice, decline_code="card_declined", amount_cents=4900):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": amount_cents,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


# --- HITL -----------------------------------------------------------------


def test_high_value_case_requires_human_review(client, seeded_invoice, stub_active_model, monkeypatch):
    """amount_at_risk_cents comes from the case's invoice (fixed at 4900 by
    the seeded_invoice fixture — a payment attempt's own amount_cents does
    not change it), so the threshold is lowered below that instead of
    trying to seed an artificially large invoice."""
    import app.services.agent_service as agent_service_module

    settings = agent_service_module.get_settings()
    monkeypatch.setattr(settings, "human_review_amount_threshold_cents", 1000)

    ingest = _ingest_failure(client, seeded_invoice, decline_code="card_declined")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["status"] == "human_review"
    assert "high_value_transaction" in decision["risk_flags"]


def test_human_review_decision_cannot_be_executed_directly(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")
    resp = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason_code"] == "human_review_required"


def test_approving_a_human_review_decision_executes_it(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["status"] == "human_review"

    resp = client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/approve",
        json={"reviewed_by": "analyst_priya", "note": "confirmed fraud with issuer"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_decision"]["status"] == "executed"
    assert body["agent_decision"]["reviewed_by"] == "analyst_priya"
    assert body["case"]["status"] == "escalated"


def test_rejecting_a_human_review_decision_does_not_execute(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()

    resp = client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/reject",
        json={"reviewed_by": "analyst_priya", "note": "handling manually outside the system"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["reviewed_by"] == "analyst_priya"

    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["status"] == "open"  # untouched — no action executed


def test_approving_an_already_approved_decision_is_refused(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/approve",
        json={"reviewed_by": "analyst", "note": None},
    )
    resp = client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/approve",
        json={"reviewed_by": "analyst2", "note": None},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason_code"] == "not_pending_review"


def test_auto_approved_decision_cannot_be_rejected(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["status"] == "auto_approved"
    resp = client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/reject",
        json={"reviewed_by": "analyst", "note": None},
    )
    assert resp.status_code == 409


# --- Trace / loop cap -------------------------------------------------------


def test_agent_trace_lists_every_decision_and_its_tool_calls(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")
    client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "r1"})
    client.post(f"/api/v1/cases/{case_id}/agent/decide")

    trace = client.get(f"/api/v1/cases/{case_id}/agent/trace").json()
    assert trace["case_id"] == case_id
    assert len(trace["decisions"]) == 2
    for decision in trace["decisions"]:
        assert len(decision["tool_calls"]) == 8
        assert decision["policy_version"] == "policy-v1"


def test_max_decisions_per_case_stops_further_automated_reasoning(client, seeded_invoice, stub_active_model, monkeypatch):
    import app.services.agent_service as agent_service_module

    settings = agent_service_module.get_settings()
    monkeypatch.setattr(settings, "max_agent_decisions_per_case", 2)

    ingest = _ingest_failure(client, seeded_invoice, decline_code="card_declined")
    case_id = ingest["case"]["id"]

    d1 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    d2 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    d3 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()

    assert d1["selected_action"] is not None
    assert d2["selected_action"] is not None
    assert d3["selected_action"] is None
    assert "max_decisions_reached" in d3["risk_flags"]
    assert d3["status"] == "human_review"


# --- Audit trail -------------------------------------------------------------


def test_full_audit_trail_sequence_for_a_successful_agent_recovery(client, seeded_invoice, stub_active_model, monkeypatch):
    from tests.conftest import FixedGateway
    from app.api.deps import get_payment_gateway

    client.app.dependency_overrides[get_payment_gateway] = lambda: FixedGateway(succeed=True)

    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")
    client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})

    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    types = [e["event_type"] for e in events]

    for expected in [
        "case_opened",
        "payment_attempt_recorded",
        "diagnosed",
        "predicted",
        "policy_evaluated",
        "agent_decided",
        "action_requested",
        "case_resolved",
        "action_outcome_recorded",
        "action_executed",
    ]:
        assert expected in types, f"missing {expected} in {types}"

    agent_event = next(e for e in events if e["event_type"] == "agent_decided")
    assert agent_event["details"]["agent_mode"] == "deterministic"
    assert agent_event["details"]["selected_action"] == "retry_payment"

    decision = client.get(f"/api/v1/cases/{case_id}/decision").json()
    assert decision["policy_version"] == "policy-v1"
    assert decision["provider_name"] == "deterministic-v1"
