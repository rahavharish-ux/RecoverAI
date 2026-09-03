"""The core promise of Phase 3: the agent reasons only over what policy
already allows, and EXECUTE independently re-validates regardless of what
any decision record says — including a decision that's been tampered with,
which is the only way to prove re-validation is real and not just "the
agent behaved" happening to look safe."""

from app.domain.enums import ActionType, DecisionStatus
from app.models.agent import AgentDecision


def _ingest_failure(client, seeded_invoice, decline_code="card_declined", amount_cents=4900):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": amount_cents,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


def test_fraud_case_agent_can_only_select_escalate(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["selected_action"] == "escalate"
    assert {a["action_type"] for a in decision["available_actions"]} == {"escalate"}
    assert "fraud_signal" in decision["risk_flags"]
    assert decision["status"] == "human_review"


def test_terminal_case_produces_no_action_and_requires_review(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="do_not_honor")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/approve",
        json={"reviewed_by": "analyst", "note": "confirmed"},
    )
    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["status"] == "escalated"

    # A fresh decision against a now-terminal case must find nothing to do.
    decision2 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision2["selected_action"] is None
    assert decision2["available_actions"] == []
    assert decision2["status"] == "human_review"


def test_retry_cap_removes_retry_from_the_agents_menu(client, seeded_invoice, stub_active_model, monkeypatch):
    import app.services.policy_service as policy_service_module
    from app.domain.policy import PolicySettings

    monkeypatch.setattr(
        policy_service_module,
        "_policy_settings",
        lambda: PolicySettings(max_retry_attempts=1, retry_cooldown_hours=0, automated_actions_enabled=True),
    )
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]

    decision1 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision1["selected_action"] == "retry_payment"
    client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "r1"})

    decision2 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert "retry_payment" not in {a["action_type"] for a in decision2["available_actions"]}
    assert decision2["selected_action"] == "escalate"


def test_cooldown_removes_retry_from_the_agents_menu(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")
    client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "r1"})

    decision2 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert "retry_payment" not in {a["action_type"] for a in decision2["available_actions"]}


def test_execute_rejects_a_tampered_decision_selecting_a_prohibited_action(
    client, seeded_invoice, stub_active_model, session_factory
):
    """Directly proves server re-validation is real: even if an
    AgentDecision row somehow said retry_payment for a fraud case (a
    hypothetical bug, or a malicious write), EXECUTE independently
    re-runs policy and refuses it — a decision record is never
    authorization by itself."""
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["selected_action"] == "escalate"

    db = session_factory()
    try:
        row = db.get(AgentDecision, decision["id"])
        row.selected_action = ActionType.RETRY_PAYMENT
        row.status = DecisionStatus.AUTO_APPROVED
        db.commit()
    finally:
        db.close()

    resp = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "fraud_signal"

    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["status"] == "open"  # nothing executed


def test_expired_card_agent_selects_method_update_never_retry(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="expired_card")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert "retry_payment" not in {a["action_type"] for a in decision["available_actions"]}
    assert decision["selected_action"] in {"request_method_update", "escalate", None}
