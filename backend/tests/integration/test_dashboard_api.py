"""API-layer smoke tests for the dashboard endpoints — the aggregation
math itself is covered in tests/unit/test_dashboard_service.py; this
confirms the routes wire up correctly and shapes match the schema."""


def _ingest_failure(client, seeded_invoice, decline_code="processor_error"):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": 4900,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


def test_summary_endpoint_on_empty_db(client):
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["revenue_at_risk_cents"] == 0
    assert body["recovery_rate"] is None


def test_summary_reflects_a_new_case(client, seeded_invoice):
    _ingest_failure(client, seeded_invoice)
    body = client.get("/api/v1/dashboard/summary").json()
    assert body["revenue_at_risk_cents"] == 4900
    assert body["active_recovery_cases"] == 1
    assert body["failed_payments"] == 1


def test_funnel_endpoint_shape(client, seeded_invoice):
    _ingest_failure(client, seeded_invoice)
    body = client.get("/api/v1/dashboard/funnel").json()
    stages = {s["stage"] for s in body}
    assert stages == {
        "failed_payment",
        "diagnosed",
        "predicted",
        "policy_eligible",
        "agent_decision",
        "recovery_action",
        "recovered",
    }


def test_failures_endpoint_after_a_fraud_case(client, seeded_invoice):
    _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    body = client.get("/api/v1/dashboard/failures").json()
    assert len(body) == 1
    assert body[0]["decline_code"] == "fraud_suspected"
    assert body[0]["retry_eligible"] is False


def test_decisions_endpoint_after_an_agent_decision(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")

    body = client.get("/api/v1/dashboard/decisions").json()
    assert len(body) == 1
    assert body[0]["case_id"] == case_id
    assert body[0]["mode_label"] == "Deterministic Decision Engine"


def test_priority_cases_endpoint(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="card_declined")
    case_id = ingest["case"]["id"]
    body = client.get("/api/v1/dashboard/priority-cases").json()
    assert any(c["case_id"] == case_id for c in body)


def test_economics_endpoint_includes_the_sandbox_disclaimer(client):
    body = client.get("/api/v1/dashboard/economics").json()
    assert "sandbox" in body["note"].lower()
    assert body["revenue_at_risk_cents"] == 0
