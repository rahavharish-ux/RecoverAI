"""Regression coverage for the Demo Center scenario orchestration endpoint
(app/api/routes/demo.py, app/services/demo_service.py).

Every test here goes through the real HTTP API and, where the point is to
prove persistence (not just a response shape), re-reads state directly
from the database via `session_factory` — the same in-memory database the
`client` fixture's overridden `get_db` dependency uses."""

from app.domain.enums import ActionOutcomeResult, ActionStatus, CaseStatus
from app.models.actions import Action, ActionOutcome
from app.models.cases import Case


def _run(client, scenario_id: str):
    resp = client.post(f"/api/v1/demo/scenarios/{scenario_id}/run")
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- 1. Isolation: repeated runs never reuse a case -------------------------


def test_running_scenario_a_twice_creates_two_separate_demo_cases(client, stub_active_model):
    first = _run(client, "A")
    second = _run(client, "A")

    first_case = first["ingest"]["case"]
    second_case = second["ingest"]["case"]
    assert first_case["id"] != second_case["id"]
    assert first_case["invoice_id"] != second_case["invoice_id"]
    # Both are fresh, independently-successful runs — proves the second
    # run was not blocked or altered by anything the first run left behind.
    assert first["execute"]["outcome"]["result"] == "succeeded"
    assert second["execute"]["outcome"]["result"] == "succeeded"


def test_every_scenario_creates_a_fresh_invoice_each_run(client, stub_active_model):
    seen_invoice_ids = set()
    for scenario_id in ("A", "B", "C", "D", "E"):
        for _ in range(2):
            body = _run(client, scenario_id)
            invoice_id = body["ingest"]["case"]["invoice_id"]
            assert invoice_id not in seen_invoice_ids
            seen_invoice_ids.add(invoice_id)


# --- 2. Scenario A: genuine, persisted successful recovery ------------------


def test_scenario_a_produces_a_genuine_persisted_successful_outcome(client, stub_active_model, session_factory):
    body = _run(client, "A")

    assert body["demo_fixture_applied"] is True
    assert body["execute"] is not None
    assert body["execute"]["action"]["action_type"] == "retry_payment"
    assert body["execute"]["outcome"]["result"] == "succeeded"
    assert body["execute"]["outcome"]["amount_recovered_cents"] == 2900
    assert body["execute"]["case"]["status"] == "resolved"

    # Re-read from the database directly — not the API response — to prove
    # this is a real persisted row, not something assembled only in memory.
    db = session_factory()
    try:
        case = db.get(Case, body["ingest"]["case"]["id"])
        assert case.status == CaseStatus.RESOLVED
        assert case.amount_recovered_cents == 2900

        action = db.query(Action).filter(Action.case_id == case.id).one()
        assert action.status == ActionStatus.EXECUTED

        outcome = db.query(ActionOutcome).filter(ActionOutcome.action_id == action.id).one()
        assert outcome.result == ActionOutcomeResult.SUCCEEDED
        assert outcome.amount_recovered_cents == 2900
    finally:
        db.close()


def test_scenario_a_fixture_does_not_alter_the_production_gateway(client, stub_active_model):
    """The `client` fixture's gateway always fails (FixedGateway(succeed=False)).
    Scenario A must still succeed (via its own explicit demo fixture) while
    every *other* retry against that same shared gateway instance keeps
    failing — proving the fixture is scoped to Scenario A's own call, not a
    global change to gateway behavior."""
    demo_body = _run(client, "A")
    assert demo_body["execute"]["outcome"]["result"] == "succeeded"
    assert client.gateway.calls == []  # the forced fixture never touched the real gateway double

    # Scenario D reuses the same profile but is NOT fixture-forced — its
    # retry must go through the real (always-failing, in this test) gateway.
    demo_d = _run(client, "D")
    assert demo_d["execute"]["outcome"]["result"] == "failed"
    assert len(client.gateway.calls) == 1


# --- 3. Production (non-demo) cases: cooldown/retry safety untouched --------


def test_seeded_case_retry_cooldown_still_enforced_alongside_demo_activity(client, seeded_invoice, stub_active_model):
    # Exercise the demo path first to prove it leaves no shared state behind.
    _run(client, "A")

    ingest = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": 4900,
            "decline_code": "processor_error",
        },
    ).json()
    case_id = ingest["case"]["id"]

    first = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert first.status_code == 201  # fails against the fixed-fail gateway, but executes

    second = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert second.status_code == 422
    assert second.json()["detail"]["reason_code"] == "cooldown_active"


# --- 4 & 5. Fraud and high-value still force HITL ----------------------------


def test_scenario_b_fraud_still_forces_hitl_and_never_executes(client, stub_active_model, session_factory):
    body = _run(client, "B")

    assert body["decision"]["status"] == "human_review"
    assert body["decision"]["requires_human_review"] is True
    assert "fraud_signal" in body["decision"]["risk_flags"]
    assert body["execute"] is None

    db = session_factory()
    try:
        case_id = body["ingest"]["case"]["id"]
        assert db.query(Action).filter(Action.case_id == case_id).count() == 0
    finally:
        db.close()


def test_scenario_e_high_value_still_forces_hitl(client, stub_active_model):
    body = _run(client, "E")

    assert body["decision"]["status"] == "human_review"
    assert body["decision"]["requires_human_review"] is True
    assert "high_value_transaction" in body["decision"]["risk_flags"]
    assert body["execute"] is None


def test_scenario_c_expired_card_never_offers_retry(client, stub_active_model):
    body = _run(client, "C")
    allowed = {a["action_type"] for a in body["decision"]["available_actions"]}
    assert "retry_payment" not in allowed


def test_scenario_d_demonstrates_cooldown_protection_without_weakening_it(client, stub_active_model):
    # Deterministic under the `client` fixture's always-failing gateway.
    body = _run(client, "D")
    assert body["execute"]["outcome"]["result"] == "failed"
    assert body["second_decision"] is not None
    retry_option = next(
        (a for a in body["second_decision"]["available_actions"] if a["action_type"] == "retry_payment"), None
    )
    assert retry_option is None  # cooldown removed it from the agent's own menu


# --- 6. Idempotency is untouched, including on a demo-created case ----------


def test_idempotency_still_works_on_a_demo_created_case(client):
    # Deliberately no `stub_active_model` here: with an active model, this
    # decline code's low recovery-probability prediction would (correctly)
    # force human review via the low_model_confidence risk flag — a
    # pre-existing, untouched safety behavior this test isn't about. With
    # no model, PREDICT silently no-ops (see ingestion_service), leaving
    # this scenario auto-approved so the idempotency mechanism itself is
    # what's under test here.
    body = _run(client, "C")  # request_method_update: auto-approved, no cooldown/retry-cap rule
    case_id = body["ingest"]["case"]["id"]

    first = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "demo-idempotency-check"})
    second = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={"client_request_id": "demo-idempotency-check"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["action"]["id"] == second.json()["action"]["id"]
    assert second.json()["deduplicated"] is True


# --- 7. Dashboard recovered revenue comes from persisted outcomes -----------


def test_dashboard_recovered_revenue_reflects_the_persisted_demo_outcome(client, stub_active_model):
    before = client.get("/api/v1/dashboard/summary").json()["recovered_revenue_cents"]
    _run(client, "A")
    after_summary = client.get("/api/v1/dashboard/summary").json()
    after_economics = client.get("/api/v1/dashboard/economics").json()

    assert after_summary["recovered_revenue_cents"] == before + 2900
    assert after_economics["recovered_revenue_cents"] == before + 2900
    assert after_economics["successful_recoveries"] >= 1


def test_unknown_scenario_id_returns_404(client):
    resp = client.post("/api/v1/demo/scenarios/Z/run")
    assert resp.status_code == 404
