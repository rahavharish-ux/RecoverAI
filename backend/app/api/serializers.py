"""Shared ORM/domain-object -> response-schema conversion, so the ingest
result shape (used by both the payment-attempts and actions routes) is
built in exactly one place."""

from sqlalchemy.orm import Session

from app.domain.decline_taxonomy import Diagnosis
from app.models.cases import PolicyDecision
from app.models.ml import MLPrediction, ModelVersion
from app.schemas.case import CaseSummaryOut
from app.schemas.ml import FeatureContributionOut, ModelVersionOut, PredictionOut
from app.schemas.payment_attempt import DiagnosisOut, PaymentAttemptIngestResult, PaymentAttemptOut
from app.schemas.policy import PolicyDecisionOut
from app.services.ingestion_service import IngestResult


def diagnosis_to_schema(diagnosis: Diagnosis | None) -> DiagnosisOut | None:
    if diagnosis is None:
        return None
    return DiagnosisOut(
        decline_code=diagnosis.decline_code,
        decline_class=diagnosis.decline_class,
        relevant_actions=list(diagnosis.relevant_actions),
        explanation=diagnosis.explanation,
    )


def policy_decision_to_schema(policy_decision: PolicyDecision | None) -> PolicyDecisionOut | None:
    if policy_decision is None:
        return None
    return PolicyDecisionOut.model_validate(policy_decision)


def ml_prediction_to_schema(db: Session, ml_prediction: MLPrediction | None) -> PredictionOut | None:
    if ml_prediction is None:
        return None
    model_version = db.get(ModelVersion, ml_prediction.model_version_id)
    return PredictionOut(
        id=ml_prediction.id,
        case_id=ml_prediction.case_id,
        payment_attempt_id=ml_prediction.payment_attempt_id,
        recovery_probability=ml_prediction.recovery_probability,
        confidence_band=ml_prediction.confidence_band,
        predicted_at=ml_prediction.predicted_at,
        model_version=ModelVersionOut.model_validate(model_version),
        top_contributions=[FeatureContributionOut(**c) for c in ml_prediction.top_contributions],
    )


def ingest_result_to_schema(db: Session, result: IngestResult) -> PaymentAttemptIngestResult:
    return PaymentAttemptIngestResult(
        payment_attempt=PaymentAttemptOut.model_validate(result.payment_attempt),
        case=CaseSummaryOut.model_validate(result.case),
        diagnosis=diagnosis_to_schema(result.diagnosis),
        prediction=ml_prediction_to_schema(db, result.ml_prediction),
        policy_decision=policy_decision_to_schema(result.policy_decision),
        deduplicated=result.deduplicated,
    )
