"""Integration tests for the PREDICT stage's wiring into the live pipeline
— using the fast StubPipeline fixture (see conftest.py), not a real
trained model. Real training correctness is covered separately in
tests/integration/test_ml_training_pipeline.py."""

from app.domain.enums import CaseEventType
from app.ml import model_registry
from app.ml.schema import FEATURE_SCHEMA_VERSION
from app.models.cases import CaseEvent
from app.models.ml import ModelVersion


def _ingest_failure(client, seeded_invoice, decline_code="card_declined"):
    payload = {
        "invoice_id": seeded_invoice["invoice_id"],
        "payment_method_id": seeded_invoice["payment_method_id"],
        "amount_cents": 4900,
        "decline_code": decline_code,
    }
    return client.post("/api/v1/payment-attempts", json=payload)


def test_ingestion_produces_a_prediction_when_a_model_is_active(client, seeded_invoice, stub_active_model):
    resp = _ingest_failure(client, seeded_invoice)
    assert resp.status_code == 201
    body = resp.json()
    assert body["prediction"] is not None
    assert 0.0 <= body["prediction"]["recovery_probability"] <= 1.0
    assert body["prediction"]["confidence_band"] in ("low", "medium", "high")
    assert body["prediction"]["model_version"]["id"] == stub_active_model


def test_ingestion_has_no_prediction_when_no_model_is_active(client, seeded_invoice):
    resp = _ingest_failure(client, seeded_invoice)
    assert resp.status_code == 201
    body = resp.json()
    assert body["prediction"] is None
    # Everything else in the Phase 1 pipeline runs exactly as before.
    assert body["case"]["status"] == "open"
    assert body["diagnosis"] is not None
    assert body["policy_decision"] is not None


def test_a_predicted_case_event_is_written(client, seeded_invoice, stub_active_model, session_factory):
    resp = _ingest_failure(client, seeded_invoice)
    case_id = resp.json()["case"]["id"]

    db = session_factory()
    try:
        events = db.query(CaseEvent).filter(CaseEvent.case_id == case_id).all()
        types = [e.event_type for e in events]
        assert CaseEventType.PREDICTED in types
        predicted_event = next(e for e in events if e.event_type == CaseEventType.PREDICTED)
        assert predicted_event.ml_prediction_id is not None
    finally:
        db.close()


def test_no_predicted_event_when_no_model_is_active(client, seeded_invoice, session_factory):
    resp = _ingest_failure(client, seeded_invoice)
    case_id = resp.json()["case"]["id"]

    db = session_factory()
    try:
        events = db.query(CaseEvent).filter(CaseEvent.case_id == case_id).all()
        assert CaseEventType.PREDICTED not in [e.event_type for e in events]
    finally:
        db.close()


def test_fraud_signal_produces_a_very_low_probability(client, seeded_invoice, stub_active_model):
    resp = _ingest_failure(client, seeded_invoice, decline_code="fraud_suspected")
    prediction = resp.json()["prediction"]
    assert prediction["recovery_probability"] < 0.10


def test_policy_eligibility_is_identical_with_or_without_an_active_model(client, seeded_invoice, stub_active_model):
    """The core safety property: Decide must reach the same conclusion
    whether or not PREDICT ran — policy never reads ml_predictions."""
    resp = _ingest_failure(client, seeded_invoice, decline_code="card_declined")
    body = resp.json()
    assert body["prediction"] is not None  # PREDICT did run
    allowed = {e["action_type"] for e in body["policy_decision"]["eligibilities"] if e["allowed"]}
    assert allowed == {"retry_payment", "request_method_update", "escalate"}


def test_missing_artifact_file_degrades_gracefully(session_factory):
    db = session_factory()
    try:
        row = ModelVersion(
            model_name="recovery_probability",
            algorithm="stub",
            version="v-missing",
            dataset_version="synthetic-v1-seed1-cust10",
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            is_calibrated=True,
            operating_threshold=0.3,
            metrics={},
            artifact_path="/nonexistent/path/model.joblib",
            is_active=True,
        )
        db.add(row)
        db.commit()

        assert model_registry.get_active_model(db) is None
    finally:
        db.close()
