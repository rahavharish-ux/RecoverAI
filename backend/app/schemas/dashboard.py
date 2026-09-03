from datetime import datetime

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    revenue_at_risk_cents: int
    recovered_revenue_cents: int
    recovery_rate: float | None
    active_recovery_cases: int
    failed_payments: int
    human_escalations: int


class FunnelStageOut(BaseModel):
    stage: str
    case_count: int
    pct_of_failed: float


class FailureCategoryOut(BaseModel):
    decline_code: str
    decline_class: str
    retry_eligible: bool
    case_count: int
    amount_involved_cents: int
    resolved_count: int
    escalated_count: int
    open_count: int


class DecisionSummaryOut(BaseModel):
    decision_id: int
    case_id: int
    amount_at_risk_cents: int
    decline_code: str | None
    recovery_probability: float | None
    selected_action: str | None
    expected_value_cents: int | None
    agent_mode: str
    mode_label: str
    risk_flags: list[str]
    status: str
    decided_at: datetime


class PriorityCaseOut(BaseModel):
    case_id: int
    amount_at_risk_cents: int
    decline_code: str | None
    recovery_probability: float | None
    expected_value_cents: int | None
    risk_level: str
    recommended_action: str | None
    requires_human_review: bool


class EconomicsOut(BaseModel):
    revenue_at_risk_cents: int
    potential_recoverable_cents: int
    recovered_revenue_cents: int
    recovery_attempts: int
    successful_recoveries: int
    human_escalations: int
    action_cost_cents: int
    net_recovery_value_cents: int
    note: str = (
        "All figures are computed over simulated sandbox data. potential_recoverable_cents is a "
        "model-estimated figure (probability x amount at risk), not a guarantee."
    )
