"""Shared, side-effect-free read helpers over case-related state. Used by
API routes, the agent's read tools (app/agent/tools.py), and the
prediction service — so there is exactly one query for, e.g., "this
customer's prior attempt stats," not three slightly different ones."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.timeutil import as_utc
from app.domain.enums import ActionStatus, AttemptStatus
from app.ml.schema import NO_PRIOR_ATTEMPT_HOURS_SENTINEL
from app.models.actions import Action
from app.models.cases import Case
from app.models.core import Invoice
from app.models.ml import MLPrediction
from app.models.payments import PaymentAttempt


def latest_diagnosed_attempt(db: Session, case_id: int) -> PaymentAttempt | None:
    return (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.case_id == case_id, PaymentAttempt.decline_code.isnot(None))
        .order_by(PaymentAttempt.attempted_at.desc())
        .first()
    )


def latest_ml_prediction(db: Session, case_id: int) -> MLPrediction | None:
    return (
        db.query(MLPrediction)
        .filter(MLPrediction.case_id == case_id)
        .order_by(MLPrediction.predicted_at.desc())
        .first()
    )


def list_actions_for_case(db: Session, case_id: int) -> list[Action]:
    return db.query(Action).filter(Action.case_id == case_id).order_by(Action.requested_at.asc()).all()


def prior_attempt_stats(db: Session, customer_id: int, before: datetime) -> tuple[int, int, float | None]:
    rows = (
        db.query(PaymentAttempt)
        .join(Invoice, PaymentAttempt.invoice_id == Invoice.id)
        .filter(Invoice.customer_id == customer_id, PaymentAttempt.attempted_at < before)
        .all()
    )
    successes = sum(1 for a in rows if a.status == AttemptStatus.SUCCEEDED)
    failures = sum(1 for a in rows if a.status == AttemptStatus.FAILED)
    avg_amount = (sum(a.amount_cents for a in rows) / len(rows)) if rows else None
    return successes, failures, avg_amount


def prior_recovery_action_count(db: Session, customer_id: int, before: datetime) -> int:
    return (
        db.query(Action)
        .join(Case, Action.case_id == Case.id)
        .filter(Case.customer_id == customer_id, Action.requested_at < before, Action.status == ActionStatus.EXECUTED)
        .count()
    )


def case_retry_context(db: Session, case_id: int, before: datetime) -> tuple[int, float]:
    prior = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.case_id == case_id, PaymentAttempt.attempted_at < before)
        .order_by(PaymentAttempt.attempted_at.desc())
        .all()
    )
    if not prior:
        return 0, NO_PRIOR_ATTEMPT_HOURS_SENTINEL
    hours_since_last = max(0.0, (before - as_utc(prior[0].attempted_at)).total_seconds() / 3600.0)
    return len(prior), hours_since_last


def executed_action_count_for_case(db: Session, case_id: int) -> int:
    return db.query(Action).filter(Action.case_id == case_id, Action.status == ActionStatus.EXECUTED).count()


def failed_attempt_count_for_case(db: Session, case_id: int) -> int:
    return (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.case_id == case_id, PaymentAttempt.status == AttemptStatus.FAILED)
        .count()
    )
