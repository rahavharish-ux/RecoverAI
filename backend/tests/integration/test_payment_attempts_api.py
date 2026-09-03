def _ingest(client, seeded_invoice, decline_code=None, amount_cents=4900, external_event_id=None):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": amount_cents,
    }
    if decline_code:
        payload["decline_code"] = decline_code
    if external_event_id:
        payload["external_event_id"] = external_event_id
    return client.post("/api/v1/payment-attempts", json=payload)


def test_ingest_failed_attempt_opens_a_case_with_diagnosis_and_policy(client, seeded_invoice):
    resp = _ingest(client, seeded_invoice, decline_code="insufficient_funds")
    assert resp.status_code == 201
    body = resp.json()
    assert body["case"]["status"] == "open"
    assert body["case"]["amount_at_risk_cents"] == 4900
    assert body["diagnosis"]["decline_class"] == "soft"
    allowed = {e["action_type"] for e in body["policy_decision"]["eligibilities"] if e["allowed"]}
    assert "retry_payment" in allowed


def test_second_failed_attempt_reuses_the_same_open_case(client, seeded_invoice):
    first = _ingest(client, seeded_invoice, decline_code="card_declined").json()
    second = _ingest(client, seeded_invoice, decline_code="card_declined").json()
    assert first["case"]["id"] == second["case"]["id"]
    assert second["payment_attempt"]["attempt_number"] == first["payment_attempt"]["attempt_number"] + 1


def test_successful_attempt_resolves_the_case(client, seeded_invoice):
    _ingest(client, seeded_invoice, decline_code="processor_error")
    resp = _ingest(client, seeded_invoice, decline_code=None)
    body = resp.json()
    assert body["case"]["status"] == "resolved"
    assert body["case"]["amount_at_risk_cents"] == 0
    assert body["case"]["amount_recovered_cents"] == 4900
    assert body["diagnosis"] is None
    assert body["policy_decision"] is None


def test_new_failure_after_resolution_opens_a_fresh_case(client, seeded_invoice):
    _ingest(client, seeded_invoice, decline_code="processor_error")
    resolved = _ingest(client, seeded_invoice, decline_code=None).json()
    reopened = _ingest(client, seeded_invoice, decline_code="card_declined").json()
    assert reopened["case"]["id"] != resolved["case"]["id"]
    assert reopened["case"]["status"] == "open"


def test_duplicate_external_event_id_is_a_no_op(client, seeded_invoice):
    first = _ingest(client, seeded_invoice, decline_code="card_declined", external_event_id="evt-1").json()
    second = _ingest(client, seeded_invoice, decline_code="card_declined", external_event_id="evt-1").json()
    assert second["deduplicated"] is True
    assert second["payment_attempt"]["id"] == first["payment_attempt"]["id"]

    events = client.get(f"/api/v1/cases/{first['case']['id']}/events").json()
    attempt_events = [e for e in events if e["event_type"] == "payment_attempt_recorded"]
    assert len(attempt_events) == 1


def test_unknown_invoice_returns_404(client):
    resp = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": 999999,
            "payment_method_id": 1,
            "amount_cents": 100,
            "decline_code": "card_declined",
        },
    )
    assert resp.status_code == 404
