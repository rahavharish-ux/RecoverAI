"""Act: request and execute a recovery action against a case.

Eligibility is re-validated here from current database state every time —
a caller's claim that an action is allowed is never trusted. Idempotency:
if the caller supplies `client_request_id`, an identical earlier request
(at any distance in time) returns its original result unchanged. Without
one, a request that arrives while an action of the same type is still
mid-flight is rejected outright (see PolicyReasonCode.ACTION_IN_FLIGHT) —
concurrent duplicates can never both execute.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.decline_taxonomy import diagnose
from app.domain.enums import (
    ActionOutcomeResult,
    ActionStatus,
    ActionType,
    AttemptSource,
    CaseEventType,
    CaseStatus,
)
from app.integrations.payment_gateway import PaymentGatewayPort
from app.models.actions import Action, ActionOutcome
from app.models.cases import Case
from app.models.core import Invoice
from app.models.payments import PaymentAttempt
from app.services import audit_service, ingestion_service, policy_service


class ActionNotEligible(Exception):
    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        self.message = message
        super().__init__(message)


def _build_idempotency_key(case_id: int, action_type: ActionType, token: str) -> str:
    return f"{case_id}:{action_type.value}:{token}"


def _next_sequence(db: Session, case_id: int, action_type: ActionType) -> int:
    return db.query(Action).filter(Action.case_id == case_id, Action.action_type == action_type).count() + 1


def _load_result_of(db: Session, action: Action) -> tuple[ActionOutcome | None, PaymentAttempt | None]:
    outcome = db.query(ActionOutcome).filter(ActionOutcome.action_id == action.id).first()
    resulting_attempt = db.get(PaymentAttempt, outcome.payment_attempt_id) if outcome else None
    return outcome, resulting_attempt


def request_action(
    db: Session,
    *,
    case: Case,
    action_type: ActionType,
    gateway: PaymentGatewayPort,
    client_request_id: str | None = None,
) -> tuple[Action, ActionOutcome | None, PaymentAttempt | None, bool]:
    now = datetime.now(timezone.utc)

    if client_request_id:
        key = _build_idempotency_key(case.id, action_type, client_request_id)
        existing = db.query(Action).filter(Action.idempotency_key == key).first()
        if existing is not None:
            outcome, resulting_attempt = _load_result_of(db, existing)
            return existing, outcome, resulting_attempt, True

    latest_attempt = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.case_id == case.id, PaymentAttempt.decline_code.isnot(None))
        .order_by(PaymentAttempt.attempted_at.desc())
        .first()
    )
    if latest_attempt is None or latest_attempt.decline_code is None:
        raise ActionNotEligible("no_active_decline", "This case has no diagnosed decline to act on.")

    diag = diagnose(latest_attempt.decline_code)
    policy_result = policy_service.evaluate_for_case(db, case=case, diagnosis=diag, now=now)
    eligibility = policy_result.eligibility_for(action_type)

    if eligibility is None or not eligibility.allowed:
        reason_code = eligibility.reason_code.value if eligibility else "unknown_action_type"
        message = eligibility.message if eligibility else "Action type is not recognized."
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.ACTION_REJECTED,
            summary=f"{action_type.value} rejected — {reason_code}.",
            details={"reason_code": reason_code, "message": message, "client_request_id": client_request_id},
        )
        db.commit()
        raise ActionNotEligible(reason_code, message)

    sequence = _next_sequence(db, case.id, action_type)
    token = client_request_id or f"seq-{sequence}-{int(now.timestamp() * 1000)}"
    idempotency_key = _build_idempotency_key(case.id, action_type, token)

    action = Action(
        case_id=case.id,
        action_type=action_type,
        status=ActionStatus.PENDING,
        idempotency_key=idempotency_key,
        sequence=sequence,
        requested_at=now,
    )
    db.add(action)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(Action).filter(Action.idempotency_key == idempotency_key).first()
        if existing is None:
            raise
        outcome, resulting_attempt = _load_result_of(db, existing)
        return existing, outcome, resulting_attempt, True

    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.ACTION_REQUESTED,
        summary=f"{action_type.value} requested.",
        details={"idempotency_key": idempotency_key},
        action_id=action.id,
    )
    db.commit()

    outcome, resulting_attempt = _execute(db, case=case, action=action, latest_attempt=latest_attempt, gateway=gateway)
    return action, outcome, resulting_attempt, False


def _execute(
    db: Session,
    *,
    case: Case,
    action: Action,
    latest_attempt: PaymentAttempt,
    gateway: PaymentGatewayPort,
) -> tuple[ActionOutcome | None, PaymentAttempt | None]:
    now = datetime.now(timezone.utc)
    outcome: ActionOutcome | None = None
    resulting_attempt: PaymentAttempt | None = None

    if action.action_type == ActionType.RETRY_PAYMENT:
        result = gateway.retry_charge(
            decline_code=latest_attempt.decline_code,
            amount_cents=latest_attempt.amount_cents,
            currency=latest_attempt.currency,
        )

        # Mark executed before re-entering the ingestion pipeline: the
        # nested policy evaluation for the resulting attempt must see this
        # retry as completed, not still pending, or it would misreport the
        # next round's eligibility as "action already in flight".
        action.status = ActionStatus.EXECUTED
        action.executed_at = now
        db.flush()

        invoice = db.get(Invoice, latest_attempt.invoice_id)
        ingest_result = ingestion_service.record_payment_attempt(
            db,
            invoice=invoice,
            payment_method_id=latest_attempt.payment_method_id,
            amount_cents=latest_attempt.amount_cents,
            currency=latest_attempt.currency,
            decline_code=None if result.succeeded else result.decline_code,
            source=AttemptSource.RETRY,
            attempted_at=now,
        )
        resulting_attempt = ingest_result.payment_attempt
        outcome = ActionOutcome(
            action_id=action.id,
            payment_attempt_id=resulting_attempt.id,
            result=ActionOutcomeResult.SUCCEEDED if result.succeeded else ActionOutcomeResult.FAILED,
            amount_recovered_cents=latest_attempt.amount_cents if result.succeeded else 0,
            occurred_at=now,
        )
        db.add(outcome)
        db.flush()
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.ACTION_OUTCOME_RECORDED,
            summary=f"Retry {'succeeded' if result.succeeded else 'failed'}.",
            details={"result": outcome.result.value, "amount_recovered_cents": outcome.amount_recovered_cents},
            action_id=action.id,
            action_outcome_id=outcome.id,
        )

    elif action.action_type == ActionType.REQUEST_METHOD_UPDATE:
        action.status = ActionStatus.EXECUTED
        action.executed_at = now
        db.flush()
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.ACTION_OUTCOME_RECORDED,
            summary="Simulated payment-method-update notification sent to customer.",
            details={"channel": "simulated_email", "template": "update_payment_method"},
            action_id=action.id,
        )

    elif action.action_type == ActionType.ESCALATE:
        action.status = ActionStatus.EXECUTED
        action.executed_at = now
        case.status = CaseStatus.ESCALATED
        case.resolved_at = now
        case.resolution_reason = "escalated"
        db.flush()
        audit_service.write_event(
            db,
            case_id=case.id,
            event_type=CaseEventType.CASE_ESCALATED,
            summary="Case escalated to human review — no further automated action will be taken.",
            details={"decline_code": latest_attempt.decline_code.value if latest_attempt.decline_code else None},
            action_id=action.id,
        )

    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.ACTION_EXECUTED,
        summary=f"{action.action_type.value} executed.",
        details={},
        action_id=action.id,
    )
    db.commit()
    db.refresh(case)
    db.refresh(action)
    return outcome, resulting_attempt
