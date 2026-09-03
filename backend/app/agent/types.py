"""Structured types every AgentProvider implementation shares — the LLM
provider and the deterministic fallback consume the same DecisionContext
and must produce the same ProviderDecision shape. Neither ever sees a raw
database session; DecisionContext is assembled once, upstream, from the
agent's read tools (see app/agent/tools.py)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.cases import Case


@dataclass(frozen=True)
class ToolContext:
    """What a tool handler needs and nothing more — a session and the case
    it's scoped to. Shared here (not in tools.py) so provider.py can depend
    on it without depending on the tools module itself."""

    db: "Session"
    case: "Case"


@dataclass(frozen=True)
class AvailableAction:
    action_type: str
    reason_code: str
    message: str
    expected_value_cents: int


@dataclass(frozen=True)
class DecisionContext:
    case_id: int
    case_status: str
    amount_at_risk_cents: int
    currency: str
    decline_code: str
    decline_class: str
    diagnosis_explanation: str
    recovery_probability: float | None
    confidence_band: str | None
    model_version: str | None
    top_contributions: list[dict]
    customer_plan_tier: str
    customer_tenure_days: float
    customer_prior_recovery_rate: float
    prior_failed_attempts_on_case: int
    executed_retry_count: int
    policy_version: str
    available_actions: list[AvailableAction]
    generated_at: datetime

    def action_types(self) -> list[str]:
        return [a.action_type for a in self.available_actions]


@dataclass(frozen=True)
class ProviderDecision:
    """What every provider must produce, however it gets there. Nothing
    here is trusted as authorization — see app/services/agent_service.py's
    EXECUTE path, which re-validates from scratch regardless."""

    selected_action: str | None  # must be one of context.action_types(), or None for "no safe action"
    reasoning_summary: str
    confidence: float
    requires_human_review: bool
    risk_flags: list[str] = field(default_factory=list)
