from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ActionOutcomeResult, ActionStatus, ActionType
from app.models.base import Base, utcnow


class Action(Base):
    """A recovery action requested against a case. `idempotency_key` is
    unique at the database level — the same (case, action_type, sequence)
    request can never produce two rows, no matter how many times it's
    submitted (see services/action_service.py)."""

    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_actions_idempotency_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    action_type: Mapped[ActionType] = mapped_column(SAEnum(ActionType, native_enum=False, length=30))
    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, native_enum=False, length=20), default=ActionStatus.PENDING
    )
    idempotency_key: Mapped[str] = mapped_column(String(140))
    sequence: Mapped[int] = mapped_column(Integer)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)


class ActionOutcome(Base):
    """The measurable financial result of a RETRY_PAYMENT action. Escalation
    and method-update requests have no financial outcome of their own — they
    are simulated notifications/handoffs, not gateway charges — so this
    table only ever holds retry results."""

    __tablename__ = "action_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id"))
    payment_attempt_id: Mapped[int] = mapped_column(ForeignKey("payment_attempts.id"))
    result: Mapped[ActionOutcomeResult] = mapped_column(SAEnum(ActionOutcomeResult, native_enum=False, length=20))
    amount_recovered_cents: Mapped[int] = mapped_column(Integer, default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
