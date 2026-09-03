from fastapi import APIRouter

from app.core.config import get_settings
from app.domain.policy import POLICY_VERSION
from app.schemas.policy import PolicyConfigOut

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("", response_model=PolicyConfigOut)
def get_policy_config() -> PolicyConfigOut:
    """Transparency endpoint: the exact, versioned rule parameters current
    decisions are being evaluated against."""
    settings = get_settings()
    return PolicyConfigOut(
        policy_version=POLICY_VERSION,
        max_retry_attempts=settings.max_retry_attempts,
        retry_cooldown_hours=settings.retry_cooldown_hours,
        automated_actions_enabled=settings.automated_actions_enabled,
        action_costs_cents=settings.action_costs_cents,
    )
