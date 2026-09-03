def _open_case(client, seeded_invoice, decline_code="card_declined", amount_cents=4900):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": amount_cents,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


def test_list_cases_includes_the_new_case(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice)
    ids = [c["id"] for c in client.get("/api/v1/cases").json()]
    assert ingest["case"]["id"] in ids


def test_list_cases_filters_by_status(client, seeded_invoice):
    _open_case(client, seeded_invoice)
    resp = client.get("/api/v1/cases", params={"status": "escalated"})
    assert resp.json() == []


def test_case_detail_404_for_unknown_case(client):
    assert client.get("/api/v1/cases/999999").status_code == 404


def test_eligibility_reflects_fraud_gate(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice, decline_code="fraud_suspected")
    body = client.get(f"/api/v1/cases/{ingest['case']['id']}/eligibility").json()
    allowed = {e["action_type"] for e in body["eligibilities"] if e["allowed"]}
    assert allowed == {"escalate"}


def test_eligibility_409_for_a_case_with_no_diagnosed_decline(client, seeded_invoice):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": 4900,
    }
    ingest = client.post("/api/v1/payment-attempts", json=payload).json()
    resp = client.get(f"/api/v1/cases/{ingest['case']['id']}/eligibility")
    assert resp.status_code == 409


def test_events_trail_is_ordered_and_complete_for_a_new_case(client, seeded_invoice):
    ingest = _open_case(client, seeded_invoice)
    events = client.get(f"/api/v1/cases/{ingest['case']['id']}/events").json()
    types = [e["event_type"] for e in events]
    assert types == ["case_opened", "payment_attempt_recorded", "diagnosed", "policy_evaluated"]


def test_policy_config_endpoint_reports_current_thresholds(client):
    body = client.get("/api/v1/policy").json()
    assert body["max_retry_attempts"] == 3
    assert body["retry_cooldown_hours"] == 24
    assert body["automated_actions_enabled"] is True
