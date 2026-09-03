"""Regression coverage for the security hardening pass:

  - the direct-action HITL bypass fix (action_service.py /
    api/routes/cases.py) — and, critically, that the legitimate agent
    HITL-approve flow for the exact same high-value case still works
  - bounded numeric/string input validation
  - dashboard limit bounds
  - safe rejection of malformed/unrecognized input (no 500s)
  - HTTP hardening: security headers, request body size cap
  - fraud protection cannot be bypassed via the direct action endpoint
  - cross-case IDOR on agent decision endpoints (decide/execute/approve/reject)
  - the central question: can an unauthenticated client, calling the API
    directly with no UI, execute a recovery action the UI would normally
    have blocked?

The LLM tool-dispatch restriction is covered separately in
tests/unit/test_agent_anthropic_provider.py, and the rate limiter's pure
counting logic in tests/unit/test_rate_limit.py.
"""

from app.models.ml import MLPrediction

# ---------------------------------------------------------------------------
# Direct-action HITL bypass — the core fix
# ---------------------------------------------------------------------------


def _ingest(client, seeded_invoice, decline_code, amount_cents=4900):
    return client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": amount_cents,
            "decline_code": decline_code,
        },
    ).json()


def test_direct_action_blocks_high_value_retry_without_review(client, seeded_invoice, monkeypatch):
    # The seeded invoice's amount is fixed at 4900 cents regardless of the
    # ingest payload (case.amount_at_risk_cents always derives from the
    # invoice) — lower the threshold below it instead of trying to raise
    # the case's amount.
    from app.core import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "human_review_amount_threshold_cents", 1000)

    ingest = _ingest(client, seeded_invoice, "card_declined", amount_cents=4900)
    case_id = ingest["case"]["id"]

    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "human_review_required"

    # The rejection itself is audited — it isn't a silent no-op.
    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    assert any(e["event_type"] == "action_rejected" for e in events)


def test_direct_action_blocks_low_confidence_retry_without_review(client, seeded_invoice, session_factory, stub_active_model):
    ingest = _ingest(client, seeded_invoice, "processor_error", amount_cents=4900)
    case_id = ingest["case"]["id"]
    attempt_id = ingest["payment_attempt"]["id"]

    # Force a low-confidence prediction directly — deterministic and
    # independent of the stub model's coarse probability buckets.
    db = session_factory()
    try:
        db.add(
            MLPrediction(
                case_id=case_id,
                payment_attempt_id=attempt_id,
                model_version_id=stub_active_model,
                recovery_probability=0.10,
                confidence_band="low",
                feature_snapshot={},
                top_contributions=[],
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "human_review_required"


def test_direct_action_still_works_for_an_ordinary_case(client, seeded_invoice):
    """The new gate must not over-block: a normal, low-value, no-prediction
    case can still be retried directly, exactly as Phase 1 intended."""
    ingest = _ingest(client, seeded_invoice, "processor_error", amount_cents=4900)
    case_id = ingest["case"]["id"]

    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 201


def test_agent_hitl_approve_flow_still_executes_a_high_value_retry(client, seeded_invoice, stub_active_model, monkeypatch):
    """The critical regression: the new direct-action gate must NEVER
    apply to a decision that has actually been through human review and
    approval — the agent's own execute()/approve_decision() path is a
    completely separate call path from the one the fix touches."""
    from app.core import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "human_review_amount_threshold_cents", 1000)

    ingest = _ingest(client, seeded_invoice, "card_declined", amount_cents=4900)
    case_id = ingest["case"]["id"]

    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["status"] == "human_review"
    assert "high_value_transaction" in decision["risk_flags"]

    approved = client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/approve",
        json={"reviewed_by": "ops-team"},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["agent_decision"]["status"] == "executed"
    assert body["action"]["action_type"] == "retry_payment"


def test_fraud_protection_cannot_be_bypassed_via_direct_action(client, seeded_invoice):
    """Fraud is enforced by the deterministic policy engine itself (not an
    agent-layer heuristic), so it was never bypassable this way — this
    locks that guarantee in with an explicit regression test."""
    ingest = _ingest(client, seeded_invoice, "fraud_suspected", amount_cents=500)
    case_id = ingest["case"]["id"]

    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "fraud_signal"


# ---------------------------------------------------------------------------
# Bounded input validation
# ---------------------------------------------------------------------------


def test_negative_amount_is_rejected(client, seeded_invoice):
    resp = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": -100,
            "decline_code": "card_declined",
        },
    )
    assert resp.status_code == 422


def test_zero_amount_is_rejected(client, seeded_invoice):
    resp = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": 0,
            "decline_code": "card_declined",
        },
    )
    assert resp.status_code == 422


def test_absurdly_large_amount_is_rejected(client, seeded_invoice):
    resp = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": 10**18,
            "decline_code": "card_declined",
        },
    )
    assert resp.status_code == 422


def test_unrecognized_action_type_is_rejected_safely(client, seeded_invoice):
    ingest = _ingest(client, seeded_invoice, "card_declined")
    case_id = ingest["case"]["id"]
    resp = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "delete_customer"})
    assert resp.status_code == 422  # Pydantic enum validation — never reaches any service code


def test_unrecognized_decline_code_is_rejected_safely(client, seeded_invoice):
    resp = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": 4900,
            "decline_code": "not_a_real_decline_code",
        },
    )
    assert resp.status_code == 422


def test_oversized_reviewer_note_is_rejected(client, seeded_invoice):
    ingest = _ingest(client, seeded_invoice, "fraud_suspected", amount_cents=500)
    case_id = ingest["case"]["id"]
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    resp = client.post(
        f"/api/v1/cases/{case_id}/agent/decisions/{decision['id']}/approve",
        json={"reviewed_by": "x" * 500, "note": "ok"},
    )
    assert resp.status_code == 422


def test_dashboard_limit_is_bounded(client):
    assert client.get("/api/v1/dashboard/decisions?limit=1000").status_code == 422
    assert client.get("/api/v1/dashboard/decisions?limit=0").status_code == 422
    assert client.get("/api/v1/dashboard/priority-cases?limit=1000").status_code == 422
    assert client.get("/api/v1/dashboard/decisions?limit=50").status_code == 200


# ---------------------------------------------------------------------------
# HTTP hardening
# ---------------------------------------------------------------------------


def test_security_headers_present(client):
    resp = client.get("/api/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"


def test_oversized_request_body_is_rejected(client, seeded_invoice):
    huge_note = "x" * 2_000_000  # 2 MB, well over the 256 KB cap
    resp = client.post(
        "/api/v1/payment-attempts",
        json={
            "invoice_id": seeded_invoice["invoice_id"],
            "payment_method_id": seeded_invoice["payment_method_id"],
            "amount_cents": 4900,
            "decline_code": "card_declined",
            "external_event_id": huge_note,
        },
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Rate limiting — proves the limiter actually enforces when NOT overridden
# (the shared `client` fixture disables it; this test deliberately builds
# its own client without that override — see tests/conftest.py).
# ---------------------------------------------------------------------------


def test_rate_limiter_returns_429_once_the_decide_limit_is_exceeded(session_factory, seeded_invoice):
    from fastapi.testclient import TestClient

    from app.api.deps import get_payment_gateway
    from app.api.routes.agent import _decide_limiter
    from app.db.session import get_db
    from app.integrations.payment_gateway import GatewayResult, PaymentGatewayPort
    from app.main import app

    class _AlwaysFail(PaymentGatewayPort):
        def retry_charge(self, *, decline_code, amount_cents, currency):
            return GatewayResult(succeeded=False, decline_code=decline_code)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    _decide_limiter._hits.clear()
    original_max = _decide_limiter.max_requests
    _decide_limiter.max_requests = 2  # keep the test fast
    try:
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_payment_gateway] = lambda: _AlwaysFail()
        # Deliberately NOT overriding _decide_limiter — this test exists to
        # prove it actually enforces when left enabled.
        local_client = TestClient(app)

        ingest = local_client.post(
            "/api/v1/payment-attempts",
            json={
                "invoice_id": seeded_invoice["invoice_id"],
                "payment_method_id": seeded_invoice["payment_method_id"],
                "amount_cents": 4900,
                "decline_code": "card_declined",
            },
        ).json()
        case_id = ingest["case"]["id"]

        first = local_client.post(f"/api/v1/cases/{case_id}/agent/decide")
        second = local_client.post(f"/api/v1/cases/{case_id}/agent/decide")
        third = local_client.post(f"/api/v1/cases/{case_id}/agent/decide")
        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429
    finally:
        _decide_limiter.max_requests = original_max
        _decide_limiter._hits.clear()
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Cross-case IDOR on agent decision endpoints
# ---------------------------------------------------------------------------


def test_decision_id_cannot_be_used_against_a_different_case(client, seeded_invoice, stub_active_model):
    """A decision belongs to exactly one case. Naming a real decision_id
    but a *different* case_id in the URL must 404, never act on it.

    case_b must be a genuinely different case (not just a second failure
    on the same open invoice, which the ingestion pipeline would fold
    back into the same case) — the demo endpoint's own fresh, isolated
    fixture is used for it rather than a second seeded_invoice ingest."""
    case_a = _ingest(client, seeded_invoice, "card_declined")["case"]["id"]
    decision_a = client.post(f"/api/v1/cases/{case_a}/agent/decide").json()

    case_b = client.post("/api/v1/demo/scenarios/B/run").json()["ingest"]["case"]["id"]
    assert case_b != case_a

    execute_cross = client.post(
        f"/api/v1/cases/{case_b}/agent/execute", json={}, params={"decision_id": decision_a["id"]}
    )
    assert execute_cross.status_code == 404

    approve_cross = client.post(
        f"/api/v1/cases/{case_b}/agent/decisions/{decision_a['id']}/approve",
        json={"reviewed_by": "attacker"},
    )
    assert approve_cross.status_code == 404

    reject_cross = client.post(
        f"/api/v1/cases/{case_b}/agent/decisions/{decision_a['id']}/reject",
        json={"reviewed_by": "attacker"},
    )
    assert reject_cross.status_code == 404


# ---------------------------------------------------------------------------
# The central question: does the API enforce what the UI merely hides?
# ---------------------------------------------------------------------------


def test_unauthenticated_direct_api_call_cannot_execute_a_ui_blocked_recovery_action(
    client, seeded_invoice, stub_active_model, monkeypatch
):
    """End-to-end proof, calling only the raw HTTP API (no browser, no UI,
    no cookies, no auth header of any kind — this repo has no auth system):
    every path that would let the UI's Case Intelligence "Execute" button
    fire a high-value retry without a human clicking Approve first is
    checked and confirmed blocked."""
    from app.core import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "human_review_amount_threshold_cents", 1000)

    ingest = _ingest(client, seeded_invoice, "card_declined", amount_cents=4900)
    case_id = ingest["case"]["id"]

    # Path 1: skip the agent entirely, hit the raw action endpoint the UI
    # never exposes for a case like this.
    direct = client.post(f"/api/v1/cases/{case_id}/actions", json={"action_type": "retry_payment"})
    assert direct.status_code == 422
    assert direct.json()["detail"]["reason_code"] == "human_review_required"

    # Path 2: go through the agent, confirm it lands in human_review...
    decision = client.post(f"/api/v1/cases/{case_id}/agent/decide").json()
    assert decision["status"] == "human_review"

    # ...then try to fire /agent/execute directly anyway, the exact request
    # the UI's "Execute" button would send if it weren't disabled.
    executed = client.post(f"/api/v1/cases/{case_id}/agent/execute", json={})
    assert executed.status_code == 409
    assert executed.json()["detail"]["reason_code"] == "human_review_required"

    # Confirm nothing was actually executed by either attempt: no Action
    # row exists for this case at all.
    actions = client.get(f"/api/v1/cases/{case_id}/actions").json()
    assert actions == []
