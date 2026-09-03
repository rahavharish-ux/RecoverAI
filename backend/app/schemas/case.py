from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import CaseEventType, CaseStatus


class CaseSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    customer_id: int
    status: CaseStatus
    amount_at_risk_cents: int
    amount_recovered_cents: int
    currency: str
    opened_at: datetime
    resolved_at: datetime | None
    resolution_reason: str | None


class CaseEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    event_type: CaseEventType
    actor: str
    summary: str
    details: dict
    payment_attempt_id: int | None
    policy_decision_id: int | None
    action_id: int | None
    action_outcome_id: int | None
    occurred_at: datetime
