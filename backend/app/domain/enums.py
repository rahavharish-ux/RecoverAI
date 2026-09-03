from enum import Enum


class DeclineCode(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    PROCESSOR_ERROR = "processor_error"
    EXPIRED_CARD = "expired_card"
    INVALID_METHOD = "invalid_method"
    DO_NOT_HONOR = "do_not_honor"
    FRAUD_SUSPECTED = "fraud_suspected"


class DeclineClass(str, Enum):
    """Coarse bucket the deterministic policy gate branches on."""

    SOFT = "soft"
    HARD = "hard"
    FRAUD = "fraud"


class AttemptStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AttemptSource(str, Enum):
    """Where a payment_attempt originated — for audit, not for policy."""

    EXTERNAL = "external"
    RETRY = "retry"


class CaseStatus(str, Enum):
    OPEN = "open"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class ActionType(str, Enum):
    RETRY_PAYMENT = "retry_payment"
    REQUEST_METHOD_UPDATE = "request_method_update"
    ESCALATE = "escalate"


class ActionStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"


class ActionOutcomeResult(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PolicyReasonCode(str, Enum):
    ELIGIBLE = "eligible"
    NOT_APPLICABLE_TO_DECLINE_REASON = "not_applicable_to_decline_reason"
    FRAUD_SIGNAL = "fraud_signal"
    HARD_DECLINE = "hard_decline"
    RETRY_LIMIT_REACHED = "retry_limit_reached"
    COOLDOWN_ACTIVE = "cooldown_active"
    CASE_TERMINAL = "case_terminal"
    ACTION_IN_FLIGHT = "action_in_flight"
    AUTOMATION_PAUSED = "automation_paused"


class CaseEventType(str, Enum):
    CASE_OPENED = "case_opened"
    PAYMENT_ATTEMPT_RECORDED = "payment_attempt_recorded"
    DIAGNOSED = "diagnosed"
    POLICY_EVALUATED = "policy_evaluated"
    ACTION_REQUESTED = "action_requested"
    ACTION_REJECTED = "action_rejected"
    ACTION_EXECUTED = "action_executed"
    ACTION_OUTCOME_RECORDED = "action_outcome_recorded"
    CASE_ESCALATED = "case_escalated"
    CASE_RESOLVED = "case_resolved"
