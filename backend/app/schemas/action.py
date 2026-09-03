from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ActionOutcomeResult, ActionStatus, ActionType
from app.schemas.case import CaseSummaryOut
from app.schemas.payment_attempt import PaymentAttemptOut


class ActionRequestIn(BaseModel):
    action_type: ActionType
    client_request_id: str | None = Field(
        default=None,
        max_length=100,
        description="Caller-supplied correlation id. Resubmitting the same "
        "case_id + action_type + client_request_id always returns the "
        "original result, however much time has passed.",
    )


class ActionOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_id: int
    payment_attempt_id: int
    result: ActionOutcomeResult
    amount_recovered_cents: int
    occurred_at: datetime


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    action_type: ActionType
    status: ActionStatus
    idempotency_key: str
    sequence: int
    requested_at: datetime
    executed_at: datetime | None
    rejection_reason: str | None


class ActionResult(BaseModel):
    action: ActionOut
    outcome: ActionOutcomeOut | None
    resulting_payment_attempt: PaymentAttemptOut | None
    case: CaseSummaryOut
    deduplicated: bool = False
