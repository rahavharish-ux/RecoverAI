"""Shared ORM/domain-object -> response-schema conversion, so the ingest
result shape (used by both the payment-attempts and actions routes) is
built in exactly one place."""

from app.domain.decline_taxonomy import Diagnosis
from app.models.cases import PolicyDecision
from app.schemas.case import CaseSummaryOut
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


def ingest_result_to_schema(result: IngestResult) -> PaymentAttemptIngestResult:
    return PaymentAttemptIngestResult(
        payment_attempt=PaymentAttemptOut.model_validate(result.payment_attempt),
        case=CaseSummaryOut.model_validate(result.case),
        diagnosis=diagnosis_to_schema(result.diagnosis),
        policy_decision=policy_decision_to_schema(result.policy_decision),
        deduplicated=result.deduplicated,
    )
