from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy import Boolean as SABoolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import CaseEventType, CaseStatus
from app.models.base import Base, utcnow


class Case(Base):
    """One recovery lifecycle for an invoice. Terminal once resolved or
    escalated — a later failure on the same invoice opens a new case rather
    than reopening this one, so a case's story never has an ambiguous end."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, native_enum=False, length=20), default=CaseStatus.OPEN
    )
    amount_at_risk_cents: Mapped[int] = mapped_column(Integer)  # see Invoice.amount_cents on naming
    amount_recovered_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="inr")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)


class CaseEvent(Base):
    """Append-only audit ledger. This table is never updated or deleted —
    only `create` and read helpers exist in the audit service (see
    services/audit_service.py) — and the Case Detail story is a direct,
    ordered render of these rows."""

    __tablename__ = "case_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    event_type: Mapped[CaseEventType] = mapped_column(SAEnum(CaseEventType, native_enum=False, length=40))
    actor: Mapped[str] = mapped_column(String(40), default="system")
    summary: Mapped[str] = mapped_column(String(300))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    payment_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("payment_attempts.id"), nullable=True)
    ml_prediction_id: Mapped[int | None] = mapped_column(ForeignKey("ml_predictions.id"), nullable=True)
    policy_decision_id: Mapped[int | None] = mapped_column(ForeignKey("policy_decisions.id"), nullable=True)
    action_id: Mapped[int | None] = mapped_column(ForeignKey("actions.id"), nullable=True)
    action_outcome_id: Mapped[int | None] = mapped_column(ForeignKey("action_outcomes.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PolicyDecision(Base):
    """One row per policy evaluation — the full eligibility table (allowed
    and prohibited, with reasons) that Decide produced at that moment."""

    __tablename__ = "policy_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    payment_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("payment_attempts.id"), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(30))
    automated_actions_enabled: Mapped[bool] = mapped_column(SABoolean, default=True)
    eligibilities: Mapped[list] = mapped_column(JSON)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
