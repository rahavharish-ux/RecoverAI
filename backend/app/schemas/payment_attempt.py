from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ActionType, AttemptSource, AttemptStatus, DeclineClass, DeclineCode
from app.schemas.case import CaseSummaryOut
from app.schemas.ml import PredictionOut
from app.schemas.policy import PolicyDecisionOut


class PaymentAttemptIngestRequest(BaseModel):
    """What a gateway webhook would send in. Omit decline_code for a
    successful attempt; include it for a failure — the taxonomy in
    app/domain/decline_taxonomy.py takes it from there."""

    invoice_id: int
    payment_method_id: int
    amount_cents: int = Field(gt=0, le=100_000_000, description="Bounded to a generous $1,000,000.00 cap.")
    currency: str = Field(default="inr", max_length=3)
    decline_code: DeclineCode | None = None
    external_event_id: str | None = Field(
        default=None,
        max_length=80,
        description="Optional caller-supplied id for de-duplicating redelivered events.",
    )
    attempted_at: datetime | None = None


class PaymentAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    payment_method_id: int
    case_id: int | None
    attempt_number: int
    amount_cents: int
    currency: str
    gateway_payment_id: str
    status: AttemptStatus
    decline_code: DeclineCode | None
    decline_class: DeclineClass | None
    source: AttemptSource
    is_simulated: bool
    attempted_at: datetime


class DiagnosisOut(BaseModel):
    decline_code: DeclineCode
    decline_class: DeclineClass
    relevant_actions: list[ActionType]
    explanation: str


class PaymentAttemptIngestResult(BaseModel):
    payment_attempt: PaymentAttemptOut
    case: CaseSummaryOut
    diagnosis: DiagnosisOut | None
    prediction: PredictionOut | None = None
    policy_decision: PolicyDecisionOut | None
    deduplicated: bool = Field(
        default=False,
        description="True if external_event_id matched an existing attempt and this was a no-op.",
    )
