from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import ActionType, PolicyReasonCode


class ActionEligibilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_type: ActionType
    allowed: bool
    reason_code: PolicyReasonCode
    message: str
    retry_after: datetime | None = None


class PolicyDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_version: str
    evaluated_at: datetime
    automated_actions_enabled: bool
    eligibilities: list[ActionEligibilityOut]


class PolicyConfigOut(BaseModel):
    policy_version: str
    max_retry_attempts: int
    retry_cooldown_hours: int
    automated_actions_enabled: bool
    note: str = (
        "Retry success rates used by the sandbox simulator are illustrative "
        "configuration values, not measured or validated recovery rates."
    )
