"""The only way anything is written to the audit ledger. Deliberately
exposes no update or delete — case_events is append-only by construction,
not by convention."""

from sqlalchemy.orm import Session

from app.domain.enums import CaseEventType
from app.models.cases import CaseEvent


def write_event(
    db: Session,
    *,
    case_id: int,
    event_type: CaseEventType,
    summary: str,
    details: dict | None = None,
    actor: str = "system",
    payment_attempt_id: int | None = None,
    policy_decision_id: int | None = None,
    action_id: int | None = None,
    action_outcome_id: int | None = None,
) -> CaseEvent:
    event = CaseEvent(
        case_id=case_id,
        event_type=event_type,
        actor=actor,
        summary=summary,
        details=details or {},
        payment_attempt_id=payment_attempt_id,
        policy_decision_id=policy_decision_id,
        action_id=action_id,
        action_outcome_id=action_outcome_id,
    )
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, case_id: int) -> list[CaseEvent]:
    return (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.occurred_at.asc(), CaseEvent.id.asc())
        .all()
    )
