from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ActionType, AgentMode, DecisionStatus
from app.schemas.action import ActionOut, ActionOutcomeOut
from app.schemas.case import CaseSummaryOut
from app.schemas.payment_attempt import PaymentAttemptOut


class AvailableActionOut(BaseModel):
    action_type: str
    reason_code: str
    message: str
    expected_value_cents: int


class AgentToolCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    tool_name: str
    input_summary: dict
    output_summary: dict
    called_at: datetime


class AgentDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    agent_mode: AgentMode
    provider_name: str
    policy_version: str
    available_actions: list[AvailableActionOut]
    expected_values_cents: dict[str, int]
    recovery_probability: float | None
    selected_action: ActionType | None
    reasoning_summary: str
    confidence: float
    risk_flags: list[str]
    requires_human_review: bool
    status: DecisionStatus
    executed_action_id: int | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    decided_at: datetime
    tool_calls: list[AgentToolCallOut] = []
    mode_label: str = ""

    def model_post_init(self, __context) -> None:
        if not self.mode_label:
            self.mode_label = "Agentic AI Decision Engine" if self.agent_mode == AgentMode.LLM else "Deterministic Decision Engine"


class AgentTraceOut(BaseModel):
    case_id: int
    decisions: list[AgentDecisionOut]


class AgentExecuteRequest(BaseModel):
    client_request_id: str | None = Field(
        default=None,
        max_length=100,
        description="Caller-supplied correlation id, forwarded to the same idempotency mechanism "
        "Phase 1 actions use — repeated execute calls for the same decision never double-execute.",
    )


class AgentReviewRequest(BaseModel):
    reviewed_by: str = Field(
        max_length=80, description="Identifier of the human reviewer — free text, no auth system yet."
    )
    note: str | None = Field(default=None, max_length=400)


class AgentExecuteResult(BaseModel):
    agent_decision: AgentDecisionOut
    action: ActionOut | None
    outcome: ActionOutcomeOut | None
    resulting_payment_attempt: PaymentAttemptOut | None
    case: CaseSummaryOut
    deduplicated: bool = False
