"""The deterministic policy engine — the Decide stage.

Pure functions over primitives: no database session, no HTTP, no LLM. Every
rule below is independently unit-testable and independently responsible for
exactly one prohibition. `evaluate()` composes them and never lets a later
rule loosen what an earlier rule already prohibited — prohibitions only
accumulate within a single evaluation.

Policy is versioned via POLICY_VERSION so a stored PolicyDecision row can
always be traced back to the exact rule set that produced it.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.decline_taxonomy import Diagnosis
from app.domain.enums import ActionType, CaseStatus, DeclineClass, PolicyReasonCode

POLICY_VERSION = "policy-v1"


@dataclass(frozen=True)
class PolicySettings:
    max_retry_attempts: int = 3
    retry_cooldown_hours: int = 24
    automated_actions_enabled: bool = True


@dataclass(frozen=True)
class PolicyInput:
    """Everything the engine needs, pre-fetched by the caller. The engine
    itself never queries anything — that keeps it fast to test exhaustively."""

    case_status: CaseStatus
    diagnosis: Diagnosis
    executed_retry_count: int
    last_retry_at: datetime | None
    now: datetime
    has_in_flight_action: dict[ActionType, bool] = field(default_factory=dict)
    settings: PolicySettings = field(default_factory=PolicySettings)


@dataclass(frozen=True)
class ActionEligibility:
    action_type: ActionType
    allowed: bool
    reason_code: PolicyReasonCode
    message: str
    retry_after: datetime | None = None


@dataclass(frozen=True)
class PolicyDecisionResult:
    policy_version: str
    evaluated_at: datetime
    automated_actions_enabled: bool
    eligibilities: tuple[ActionEligibility, ...]

    @property
    def allowed_actions(self) -> tuple[ActionType, ...]:
        return tuple(e.action_type for e in self.eligibilities if e.allowed)

    @property
    def prohibited_actions(self) -> tuple[ActionEligibility, ...]:
        return tuple(e for e in self.eligibilities if not e.allowed)

    def eligibility_for(self, action_type: ActionType) -> ActionEligibility | None:
        return next((e for e in self.eligibilities if e.action_type == action_type), None)


def _terminal_reason(status: CaseStatus) -> str:
    if status == CaseStatus.ESCALATED:
        return "This case has already been escalated to a human and is no longer eligible for automated actions."
    return "This case has already been resolved; no further action is eligible."


def evaluate(policy_input: PolicyInput) -> PolicyDecisionResult:
    settings = policy_input.settings
    diagnosis = policy_input.diagnosis
    eligibilities: list[ActionEligibility] = []

    for action_type in ActionType:
        eligibilities.append(_evaluate_action(action_type, policy_input, settings, diagnosis))

    return PolicyDecisionResult(
        policy_version=POLICY_VERSION,
        evaluated_at=policy_input.now,
        automated_actions_enabled=settings.automated_actions_enabled,
        eligibilities=tuple(eligibilities),
    )


def _evaluate_action(
    action_type: ActionType,
    policy_input: PolicyInput,
    settings: PolicySettings,
    diagnosis: Diagnosis,
) -> ActionEligibility:
    # Rule 1 — kill switch. Nothing is ever allowed while automation is paused.
    if not settings.automated_actions_enabled:
        return ActionEligibility(
            action_type=action_type,
            allowed=False,
            reason_code=PolicyReasonCode.AUTOMATION_PAUSED,
            message="Automated actions are globally paused.",
        )

    # Rule 2 — a resolved or escalated case accepts no further automated action.
    if policy_input.case_status != CaseStatus.OPEN:
        return ActionEligibility(
            action_type=action_type,
            allowed=False,
            reason_code=PolicyReasonCode.CASE_TERMINAL,
            message=_terminal_reason(policy_input.case_status),
        )

    # Rule 3 — an identical action already in flight for this case is never re-issued.
    if policy_input.has_in_flight_action.get(action_type, False):
        return ActionEligibility(
            action_type=action_type,
            allowed=False,
            reason_code=PolicyReasonCode.ACTION_IN_FLIGHT,
            message=f"A {action_type.value} action is already in flight for this case.",
        )

    # Rule 4 — fraud signal: only escalation is ever relevant or allowed.
    if diagnosis.decline_class == DeclineClass.FRAUD and action_type != ActionType.ESCALATE:
        return ActionEligibility(
            action_type=action_type,
            allowed=False,
            reason_code=PolicyReasonCode.FRAUD_SIGNAL,
            message="This attempt was flagged as a suspected fraud signal — no "
            "automated recovery action is taken; escalation only.",
        )

    # Rule 5 — decline-code relevance table (see decline_taxonomy.py).
    if action_type not in diagnosis.relevant_actions:
        return ActionEligibility(
            action_type=action_type,
            allowed=False,
            reason_code=PolicyReasonCode.NOT_APPLICABLE_TO_DECLINE_REASON,
            message=f"{action_type.value} is not applicable to a "
            f"{diagnosis.decline_code.value} decline.",
        )

    # Rule 6 — hard decline: retries are never allowed (only reachable here for
    # actions the relevance table already marked relevant, e.g. escalate/method-update).
    if diagnosis.decline_class == DeclineClass.HARD and action_type == ActionType.RETRY_PAYMENT:
        return ActionEligibility(
            action_type=action_type,
            allowed=False,
            reason_code=PolicyReasonCode.HARD_DECLINE,
            message="This is a hard decline — retrying the same payment method cannot succeed.",
        )

    # Rules 7 & 8 apply only to RETRY_PAYMENT.
    if action_type == ActionType.RETRY_PAYMENT:
        if policy_input.executed_retry_count >= settings.max_retry_attempts:
            return ActionEligibility(
                action_type=action_type,
                allowed=False,
                reason_code=PolicyReasonCode.RETRY_LIMIT_REACHED,
                message=f"The retry limit of {settings.max_retry_attempts} attempts "
                "has already been reached for this case.",
            )

        if policy_input.last_retry_at is not None:
            retry_after = policy_input.last_retry_at + timedelta(hours=settings.retry_cooldown_hours)
            if policy_input.now < retry_after:
                return ActionEligibility(
                    action_type=action_type,
                    allowed=False,
                    reason_code=PolicyReasonCode.COOLDOWN_ACTIVE,
                    message=f"A minimum {settings.retry_cooldown_hours}h cooldown is "
                    "still active since the last retry.",
                    retry_after=retry_after,
                )

    return ActionEligibility(
        action_type=action_type,
        allowed=True,
        reason_code=PolicyReasonCode.ELIGIBLE,
        message=f"{action_type.value} is currently eligible for this case.",
    )
