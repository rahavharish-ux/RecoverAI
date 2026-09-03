"""Detect + Diagnose + Predict (+ Decide, for failures) for one payment
attempt — whether it arrived as an external gateway event or was generated
internally by executing a retry action. Both paths funnel through
`record_payment_attempt` so a retry's result is diagnosed, scored, policy-
evaluated, and audited exactly like any attempt a real gateway would
report."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.decline_taxonomy import Diagnosis, diagnose
from app.domain.enums import AttemptSource, AttemptStatus, CaseEventType, CaseStatus, DeclineCode
from app.models.cases import Case, PolicyDecision
from app.models.core import Invoice
from app.models.ml import MLPrediction
from app.models.payments import PaymentAttempt
from app.services import audit_service, policy_service, prediction_service

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    payment_attempt: PaymentAttempt
    case: Case
    diagnosis: Diagnosis | None
    ml_prediction: MLPrediction | None
    policy_decision: PolicyDecision | None
    deduplicated: bool


def _next_attempt_number(db: Session, invoice_id: int) -> int:
    return db.query(PaymentAttempt).filter(PaymentAttempt.invoice_id == invoice_id).count() + 1


def _get_or_create_open_case(db: Session, invoice: Invoice, now: datetime) -> Case:
    case = (
        db.query(Case)
        .filter(Case.invoice_id == invoice.id, Case.status == CaseStatus.OPEN)
        .order_by(Case.opened_at.desc())
        .first()
    )
    if case is not None:
        return case

    case = Case(
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        status=CaseStatus.OPEN,
        amount_at_risk_cents=invoice.amount_cents,
        currency=invoice.currency,
        opened_at=now,
    )
    db.add(case)
    db.flush()
    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.CASE_OPENED,
        summary=f"Case opened for invoice #{invoice.id} — "
        f"{invoice.amount_cents / 100:.2f} {invoice.currency.upper()} at risk.",
        details={"invoice_id": invoice.id, "amount_cents": invoice.amount_cents, "currency": invoice.currency},
    )
    return case


def _resolve_case(db: Session, case: Case, *, amount_recovered_cents: int, reason: str, now: datetime) -> None:
    case.status = CaseStatus.RESOLVED
    case.resolved_at = now
    case.resolution_reason = reason
    case.amount_recovered_cents = amount_recovered_cents
    case.amount_at_risk_cents = 0
    db.flush()
    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.CASE_RESOLVED,
        summary=f"Case resolved — {reason}.",
        details={"amount_recovered_cents": amount_recovered_cents, "reason": reason},
    )


def record_payment_attempt(
    db: Session,
    *,
    invoice: Invoice,
    payment_method_id: int,
    amount_cents: int,
    currency: str,
    decline_code: DeclineCode | None,
    source: AttemptSource,
    external_event_id: str | None = None,
    attempted_at: datetime | None = None,
) -> IngestResult:
    now = attempted_at or datetime.now(timezone.utc)

    if external_event_id:
        existing = (
            db.query(PaymentAttempt).filter(PaymentAttempt.external_event_id == external_event_id).first()
        )
        if existing is not None:
            case = db.get(Case, existing.case_id)
            diag = diagnose(existing.decline_code) if existing.decline_code else None
            latest_decision = (
                db.query(PolicyDecision)
                .filter(PolicyDecision.case_id == case.id)
                .order_by(PolicyDecision.evaluated_at.desc())
                .first()
            )
            return IngestResult(existing, case, diag, None, latest_decision, deduplicated=True)

    is_success = decline_code is None
    status = AttemptStatus.SUCCEEDED if is_success else AttemptStatus.FAILED
    decline_class = diagnose(decline_code).decline_class if decline_code else None

    case = _get_or_create_open_case(db, invoice, now)

    attempt = PaymentAttempt(
        invoice_id=invoice.id,
        payment_method_id=payment_method_id,
        case_id=case.id,
        attempt_number=_next_attempt_number(db, invoice.id),
        amount_cents=amount_cents,
        currency=currency,
        status=status,
        decline_code=decline_code,
        decline_class=decline_class,
        source=source,
        is_simulated=True,
        external_event_id=external_event_id,
        attempted_at=now,
    )
    db.add(attempt)
    db.flush()

    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.PAYMENT_ATTEMPT_RECORDED,
        summary=(
            f"Attempt #{attempt.attempt_number} succeeded."
            if is_success
            else f"Attempt #{attempt.attempt_number} failed — {decline_code.value}."
        ),
        details={"amount_cents": amount_cents, "currency": currency, "source": source.value},
        payment_attempt_id=attempt.id,
    )

    diag: Diagnosis | None = None
    ml_prediction: MLPrediction | None = None
    policy_row: PolicyDecision | None = None

    if is_success:
        _resolve_case(db, case, amount_recovered_cents=amount_cents, reason="payment_succeeded", now=now)
    else:
        diag = diagnose(decline_code)
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.DIAGNOSED,
            summary=f"Diagnosed as a {diag.decline_class.value} decline ({diag.decline_code.value}).",
            details={
                "decline_code": diag.decline_code.value,
                "decline_class": diag.decline_class.value,
                "explanation": diag.explanation,
            },
            payment_attempt_id=attempt.id,
        )

        # PREDICT: advisory only. If no model is trained yet, or anything
        # about scoring fails, this silently no-ops — Decide below runs off
        # `diag` alone and has no idea whether a prediction exists.
        try:
            prediction_result = prediction_service.predict_recovery_probability(
                db, case=case, attempt=attempt, diagnosis=diag
            )
        except Exception:
            logger.exception(
                "PREDICT stage failed for case_id=%s payment_attempt_id=%s — continuing without a prediction.",
                case.id,
                attempt.id,
            )
            prediction_result = None

        if prediction_result is not None:
            ml_prediction = prediction_result.ml_prediction
            audit_service.write_event(
                db,
                case_id=case.id,
                event_type=CaseEventType.PREDICTED,
                summary=f"Estimated retry-success probability: {ml_prediction.recovery_probability:.0%} "
                f"({ml_prediction.confidence_band} confidence).",
                details={
                    "model_version_id": prediction_result.model_version.id,
                    "algorithm": prediction_result.model_version.algorithm,
                    "recovery_probability": ml_prediction.recovery_probability,
                    "confidence_band": ml_prediction.confidence_band,
                },
                payment_attempt_id=attempt.id,
                ml_prediction_id=ml_prediction.id,
            )

        policy_result = policy_service.evaluate_for_case(db, case=case, diagnosis=diag, now=now)
        policy_row = policy_service.persist_decision(
            db, case_id=case.id, payment_attempt_id=attempt.id, result=policy_result
        )
        allowed = ", ".join(a.value for a in policy_result.allowed_actions)
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.POLICY_EVALUATED,
            summary=f"Policy allows: {allowed or 'nothing — escalation required'}.",
            details={"policy_decision_id": policy_row.id},
            payment_attempt_id=attempt.id,
            policy_decision_id=policy_row.id,
        )

    db.commit()
    db.refresh(case)
    db.refresh(attempt)
    return IngestResult(attempt, case, diag, ml_prediction, policy_row, deduplicated=False)
