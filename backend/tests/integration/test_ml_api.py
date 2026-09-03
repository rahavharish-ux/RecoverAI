"""API tests for the ML endpoints: model metadata, evaluation summary, and
per-case prediction read/refresh — using the fast StubPipeline fixture."""


def _ingest_failure(client, seeded_invoice, decline_code="card_declined"):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": 4900,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


def test_model_metadata_404_when_no_model_trained(client):
    assert client.get("/api/v1/ml/model").status_code == 404


def test_model_metadata_returns_active_model(client, stub_active_model):
    resp = client.get("/api/v1/ml/model")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == stub_active_model
    assert body["is_active"] is True
    assert body["algorithm"] == "stub"


def test_evaluation_404_when_no_model_trained(client):
    assert client.get("/api/v1/ml/evaluation").status_code == 404


def test_evaluation_returns_the_stored_report(client, stub_active_model):
    resp = client.get("/api/v1/ml/evaluation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_version"]["id"] == stub_active_model
    assert "note" in body["report"]


def test_case_prediction_404_before_any_prediction(client, seeded_invoice):
    ingest = _ingest_failure(client, seeded_invoice)
    resp = client.get(f"/api/v1/cases/{ingest['case']['id']}/prediction")
    assert resp.status_code == 404


def test_case_prediction_returned_after_ingestion(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice)
    resp = client.get(f"/api/v1/cases/{ingest['case']['id']}/prediction")
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["recovery_probability"] <= 1.0
    assert body["top_contributions"]
    assert "retry_payment" in body["expected_values_cents"]


def test_prediction_endpoint_404_for_unknown_case(client):
    assert client.get("/api/v1/cases/999999/prediction").status_code == 404


def test_refresh_prediction_endpoint_recomputes(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice)
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/predict")
    assert resp.status_code == 201
    assert resp.json()["case_id"] == case_id


def test_refresh_prediction_503_without_a_model(client, seeded_invoice):
    ingest = _ingest_failure(client, seeded_invoice)
    resp = client.post(f"/api/v1/cases/{ingest['case']['id']}/predict")
    assert resp.status_code == 503


def test_refresh_prediction_409_for_a_case_with_no_diagnosed_decline(client, seeded_invoice, stub_active_model):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": 4900,
    }
    ingest = client.post("/api/v1/payment-attempts", json=payload).json()
    resp = client.post(f"/api/v1/cases/{ingest['case']['id']}/predict")
    assert resp.status_code == 409


def test_invalid_action_type_returns_422(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice)
    resp = client.post(f"/api/v1/cases/{ingest['case']['id']}/actions", json={"action_type": "not_a_real_action"})
    assert resp.status_code == 422


def test_invalid_decline_code_returns_422(client, seeded_invoice):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": 4900,
        "decline_code": "not_a_real_decline_code",
    }
    resp = client.post("/api/v1/payment-attempts", json=payload)
    assert resp.status_code == 422
