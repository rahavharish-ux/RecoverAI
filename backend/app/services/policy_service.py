"""Assembles database state into the pure `PolicyInput` the domain engine
needs, runs it, and persists the resulting `PolicyDecision` row. The engine
itself (app/domain/policy.py) never touches the database."""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import as_utc
from app.domain.decline_taxonomy import Diagnosis
from app.domain.enums import ActionStatus, ActionType
from app.domain.policy import PolicyDecisionResult, PolicyInput, PolicySettings
from app.domain.policy import evaluate as evaluate_policy
from app.models.actions import Action
from app.models.cases import Case, PolicyDecision


def _policy_settings() -> PolicySettings:
    settings = get_settings()
    return PolicySettings(
        max_retry_attempts=settings.max_retry_attempts,
        retry_cooldown_hours=settings.retry_cooldown_hours,
        automated_actions_enabled=settings.automated_actions_enabled,
    )


def _executed_retry_stats(db: Session, case_id: int) -> tuple[int, datetime | None]:
    count = (
        db.query(func.count(Action.id))
        .filter(
            Action.case_id == case_id,
            Action.action_type == ActionType.RETRY_PAYMENT,
            Action.status == ActionStatus.EXECUTED,
        )
        .scalar()
    ) or 0
    last_retry_at = (
        db.query(func.max(Action.executed_at))
        .filter(
            Action.case_id == case_id,
            Action.action_type == ActionType.RETRY_PAYMENT,
            Action.status == ActionStatus.EXECUTED,
        )
        .scalar()
    )
    return count, as_utc(last_retry_at)


def _in_flight_map(db: Session, case_id: int) -> dict[ActionType, bool]:
    pending_types = {
        row[0]
        for row in db.query(Action.action_type)
        .filter(Action.case_id == case_id, Action.status == ActionStatus.PENDING)
        .all()
    }
    return {action_type: action_type in pending_types for action_type in ActionType}


def evaluate_for_case(
    db: Session, *, case: Case, diagnosis: Diagnosis, now: datetime | None = None
) -> PolicyDecisionResult:
    now = now or datetime.now(timezone.utc)
    executed_retry_count, last_retry_at = _executed_retry_stats(db, case.id)
    policy_input = PolicyInput(
        case_status=case.status,
        diagnosis=diagnosis,
        executed_retry_count=executed_retry_count,
        last_retry_at=last_retry_at,
        now=now,
        has_in_flight_action=_in_flight_map(db, case.id),
        settings=_policy_settings(),
    )
    return evaluate_policy(policy_input)


def persist_decision(
    db: Session, *, case_id: int, payment_attempt_id: int | None, result: PolicyDecisionResult
) -> PolicyDecision:
    row = PolicyDecision(
        case_id=case_id,
        payment_attempt_id=payment_attempt_id,
        policy_version=result.policy_version,
        automated_actions_enabled=result.automated_actions_enabled,
        eligibilities=[
            {
                "action_type": e.action_type.value,
                "allowed": e.allowed,
                "reason_code": e.reason_code.value,
                "message": e.message,
                "retry_after": e.retry_after.isoformat() if e.retry_after else None,
            }
            for e in result.eligibilities
        ],
        evaluated_at=result.evaluated_at,
    )
    db.add(row)
    db.flush()
    return row
