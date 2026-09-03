from app.api.deps import get_payment_gateway
from app.domain.enums import ActionStatus, ActionType
from app.domain.policy import PolicySettings
from app.models.actions import Action
from tests.conftest import FixedGateway


def _open_case(client, seeded_invoice, decline_code="card_declined", amount_cents=4900):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": amount_cents,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


# --- Eligibility is re-validated server-side, never trusted from the caller --


def test_action_rejected_for_a_fraud_case(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "fraud_signal"

    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    assert any(e["event_type"] == "action_rejected" for e in events)


def test_retry_prohibited_for_expired_card(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="expired_card")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "not_applicable_to_decline_reason"


def test_kill_switch_blocks_all_actions(client, seeded_invoice, monkeypatch):
    import app.services.policy_service as policy_service_module

    monkeypatch.setattr(
        policy_service_module,
        "_policy_settings",
        lambda: PolicySettings(max_retry_attempts=3, retry_cooldown_hours=24, automated_actions_enabled=False),
    )
    ingest = _open_case(client, seeded_invoice, decline_code="card_declined")
    resp = client.post(f"/api/v1/cases/{ingest['case']['id']}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "automation_paused"


# --- Act + Measure: retry outcomes --------------------------------------------


def test_retry_records_a_failed_outcome_and_leaves_case_open(client, seeded_invoice):
    # the `client` fixture's default gateway always fails
    ingest = _open_case(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["outcome"]["result"] == "failed"
    assert body["case"]["status"] == "open"

    actions = client.get(f"/api/v1/cases/{case_id}/actions").json()
    assert len(actions) == 1
    assert actions[0]["status"] == "executed"


def test_retry_resolves_the_case_on_success(client, seeded_invoice):
    client.app.dependency_overrides[get_payment_gateway] = lambda: FixedGateway(succeed=True)
    ingest = _open_case(client, seeded_invoice, decline_code="insufficient_funds")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    body = resp.json()
    assert body["outcome"]["result"] == "succeeded"
    assert body["case"]["status"] == "resolved"
    assert body["case"]["amount_recovered_cents"] == 4900

    again = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert again.status_code == 422
    assert again.json()["detail"]["reason_code"] == "case_terminal"


def test_escalate_marks_case_escalated_with_no_financial_outcome(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="do_not_honor")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "escalate"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["case"]["status"] == "escalated"
    assert body["outcome"] is None

    again = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "escalate"})
    assert again.status_code == 422
    assert again.json()["detail"]["reason_code"] == "case_terminal"


def test_method_update_has_no_financial_outcome_and_leaves_case_open(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="expired_card")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "request_method_update"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["outcome"] is None
    assert body["case"]["status"] == "open"


# --- Retry caps and cooldown, driven end to end -------------------------------


def test_second_retry_is_blocked_by_cooldown_by_default(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    first = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert first.status_code == 201
    second = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert second.status_code == 422
    assert second.json()["detail"]["reason_code"] == "cooldown_active"


def test_retry_limit_is_enforced_end_to_end(client, seeded_invoice, monkeypatch):
    import app.services.policy_service as policy_service_module

    monkeypatch.setattr(
        policy_service_module,
        "_policy_settings",
        lambda: PolicySettings(max_retry_attempts=3, retry_cooldown_hours=0, automated_actions_enabled=True),
    )
    ingest = _open_case(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]

    for i in range(3):
        resp = client.post(
            f"/api/v1/cases/{case_id}/actions",
            json={"action_type": "retry_payment", "client_request_id": f"attempt-{i}"},
        )
        assert resp.status_code == 201, resp.text

    resp = client.post(
        f"/api/v1/cases/{case_id}/actions",
        json={"action_type": "retry_payment", "client_request_id": "attempt-final"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "retry_limit_reached"


# --- Idempotency ----------------------------------------------------------------


def test_duplicate_client_request_id_is_a_no_op(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    payload = {"action_type": "retry_payment", "client_request_id": "dup-key-1"}

    first = client.post(f"/api/v1/cases/{case_id}/actions", json=payload).json()
    second = client.post(f"/api/v1/cases/{case_id}/actions", json=payload).json()
    assert second["deduplicated"] is True
    assert second["action"]["id"] == first["action"]["id"]

    actions = client.get(f"/api/v1/cases/{case_id}/actions").json()
    assert len(actions) == 1

    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    assert len([e for e in events if e["event_type"] == "action_executed"]) == 1


def test_in_flight_pending_action_blocks_a_new_request_of_the_same_type(client, seeded_invoice, session_factory):
    """Simulates a crash between 'action created as PENDING' and
    'executed' — a duplicate request must be rejected outright, never
    trigger a second execution."""
    ingest = _open_case(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]

    db = session_factory()
    try:
        db.add(
            Action(
                case_id=case_id,
                action_type=ActionType.RETRY_PAYMENT,
                status=ActionStatus.PENDING,
                idempotency_key=f"{case_id}:retry_payment:crashed",
                sequence=1,
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "action_in_flight"
