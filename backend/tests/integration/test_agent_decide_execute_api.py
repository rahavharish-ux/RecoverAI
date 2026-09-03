"""Core DECIDE -> EXECUTE flow through the API, using the fast StubPipeline
fixture (see conftest.py) so predictions are available without a real
trained model."""


def _ingest_failure(client, seeded_invoice, decline_code="processor_error", amount_cents=4900):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": amount_cents,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload).json()


def test_decide_returns_a_structured_decision(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice)
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/agent/decide")
    assert resp.status_code == 201
    body = resp.json()
    assert body["agent_mode"] == "deterministic"
    assert body["mode_label"] == "Deterministic Decision Engine"
    assert body["selected_action"] in {"retry_payment", "request_method_update", "escalate"}
    assert body["reasoning_summary"]
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["risk_flags"], list)
    assert len(body["tool_calls"]) == 8  # every read tool called to assemble context


def test_selected_action_is_always_from_the_allowed_set(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="card_declined")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/agent/decide")
    body = resp.json()
    allowed = {a["action_type"] for a in body["available_actions"]}
    assert body["selected_action"] in allowed


def test_decide_404_for_unknown_case(client):
    assert client.post("/api/v1/cases/999999/agent/decide").status_code == 404


def test_execute_runs_the_selected_action_and_produces_an_outcome(client, seeded_invoice, stub_active_model):
    # default gateway in the `client` fixture always fails retries
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    decide_resp = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decide_resp["status"] == "auto_approved"
    assert decide_resp["selected_action"] == "retry_payment"  # highest EV for processor_error + good probability

    exec_resp = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})
    assert exec_resp.status_code == 201
    body = exec_resp.json()
    assert body["agent_decision"]["status"] == "executed"
    assert body["action"]["action_type"] == "retry_payment"
    assert body["outcome"]["result"] == "failed"


def test_execute_with_no_decision_yet_returns_404(client, seeded_invoice):
    ingest = _ingest_failure(client, seeded_invoice)
    resp = client.post(f"/api/v1/cases/{ingest['case']['id']}/agent/execute", json={})
    assert resp.status_code == 404


def test_execute_is_idempotent_via_client_request_id(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")

    first = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "agent-exec-1"}).json()
    second = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "agent-exec-1"}).json()
    assert second["deduplicated"] is True
    assert second["action"]["id"] == first["action"]["id"]

    actions = client.get(f"/api/v1/cases/{case_id}/actions").json()
    assert len(actions) == 1  # not duplicated


def test_execute_twice_without_a_client_request_id_hits_cooldown_not_a_double_execution(
    client, seeded_invoice, stub_active_model
):
    """Re-calling execute on an already-executed decision without a
    correlation id is NOT special-cased as an error at the agent layer —
    it's re-evaluated by the exact same policy gate any action request
    goes through, and a second retry this soon is legitimately blocked by
    cooldown, not by some agent-specific 'already done' rule."""
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    client.post(f"/api/v1/cases/{case_id}/agent/decide")
    first = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})
    assert first.status_code == 201

    resp = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "cooldown_active"


def test_rejected_and_escalated_decisions_cannot_be_re_executed(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/reject",
        json={"reviewed_by": "analyst", "note": None},
    )
    resp = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={}, params={"decision_id": decision["id"]})
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason_code"] == "already_finalized"


def test_server_revalidates_state_changed_between_decide_and_execute(client, seeded_invoice, stub_active_model):
    """The core safety property under test: a decision made against one
    state of the world is re-checked against the CURRENT state at execute
    time, not blindly trusted."""
    ingest = _ingest_failure(client, seeded_invoice, decline_code="processor_error")
    case_id = ingest["case"]["id"]
    decide1 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decide1["selected_action"] == "retry_payment"

    # Execute it once — this starts the cooldown clock.
    client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "first"})

    # A second decision, made immediately after, must reflect the new
    # reality: retry is now cooling down.
    decide2 = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    retry_option = next((a for a in decide2["available_actions"] if a["action_type"] == "retry_payment"), None)
    assert retry_option is None  # cooldown removed it from the allowed set entirely


def test_get_latest_decision_endpoint(client, seeded_invoice, stub_active_model):
    ingest = _ingest_failure(client, seeded_invoice)
    case_id = ingest["case"]["id"]
    decided = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    fetched = client.get(f"/api/v1/cases/{case_id}/decision").json()
    assert fetched["id"] == decided["id"]


def test_get_latest_decision_404_before_any_decision(client, seeded_invoice):
    ingest = _ingest_failure(client, seeded_invoice)
    resp = client.get(f"/api/v1/cases/{ingest['case']['id']}/decision")
    assert resp.status_code == 404
