from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Boolean as SABoolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ActionType, AgentMode, DecisionStatus
from app.models.base import Base, utcnow


class AgentDecision(Base):
    """One row per DECIDE-stage run. `selected_action` is nullable — it's
    null when no policy-allowed action existed to choose from. Nothing here
    is authorization to act: see AgentToolCall's write tools and
    services/agent_service.py's EXECUTE path, which re-validates everything
    from scratch regardless of what's recorded here."""

    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    payment_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("payment_attempts.id"), nullable=True)
    ml_prediction_id: Mapped[int | None] = mapped_column(ForeignKey("ml_predictions.id"), nullable=True)
    policy_decision_id: Mapped[int | None] = mapped_column(ForeignKey("policy_decisions.id"), nullable=True)

    agent_mode: Mapped[AgentMode] = mapped_column(SAEnum(AgentMode, native_enum=False, length=20))
    provider_name: Mapped[str] = mapped_column(String(60))
    policy_version: Mapped[str] = mapped_column(String(30))

    available_actions: Mapped[list] = mapped_column(JSON)
    expected_values_cents: Mapped[dict] = mapped_column(JSON)
    recovery_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    selected_action: Mapped[ActionType | None] = mapped_column(
        SAEnum(ActionType, native_enum=False, length=30), nullable=True
    )
    reasoning_summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    risk_flags: Mapped[list] = mapped_column(JSON)
    requires_human_review: Mapped[bool] = mapped_column(SABoolean, default=False)

    status: Mapped[DecisionStatus] = mapped_column(
        SAEnum(DecisionStatus, native_enum=False, length=20), default=DecisionStatus.AUTO_APPROVED
    )
    executed_action_id: Mapped[int | None] = mapped_column(ForeignKey("actions.id"), nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentToolCall(Base):
    """One row per tool invocation made while producing an AgentDecision —
    the granular trace of what the agent actually looked at (or, in
    deterministic mode, what was looked at on its behalf). Inputs/outputs
    are pre-sanitized summaries (see app/agent/tools.py) — never secrets,
    never full card data, which doesn't exist in this system anyway."""

    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_decision_id: Mapped[int] = mapped_column(ForeignKey("agent_decisions.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(60))
    input_summary: Mapped[dict] = mapped_column(JSON)
    output_summary: Mapped[dict] = mapped_column(JSON)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
