"""The agent's only interface to case data — no provider, LLM or
deterministic, ever queries the database directly. Every tool has a
strict Pydantic input and output schema.

READ tools (safe to call freely, used to assemble app.agent.types.
DecisionContext and, for the LLM provider, individually callable during
its bounded tool-use loop — see app/agent/anthropic_provider.py):
  get_transaction, get_customer_history, analyze_payment_failure,
  calculate_recovery_probability, check_retry_eligibility,
  get_recovery_policy, get_case_state, calculate_expected_recovery_value

WRITE tools are split into two kinds:
  - Financial/state-changing (initiate_payment_retry, generate_payment_link,
    escalate_to_human): map onto the three existing app.domain.enums.
    ActionType values and are never invoked from here — they exist as
    schema-defined capabilities the agent's decision draws from;
    app/services/agent_service.py's EXECUTE step performs the actual write
    via the unchanged Phase 1 action_service.request_action, after full
    re-validation.
  - Non-financial logging (create_recovery_message, record_audit_event):
    write a case_event directly, no policy gate needed since they don't
    move money or change case status.
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agent.types import ToolContext
from app.core.config import get_settings
from app.core.timeutil import as_utc
from app.domain.decline_taxonomy import diagnose
from app.domain.enums import CaseEventType
from app.models.core import Customer
from app.services import audit_service, case_query, policy_service, prediction_service

__all__ = ["ToolContext", "ToolError", "ToolSpec", "TOOL_REGISTRY", "READ_TOOL_SPECS", "WRITE_TOOL_SPECS", "call_tool"]


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------- schemas --


class EmptyInput(BaseModel):
    pass


class TransactionOut(BaseModel):
    invoice_id: int
    payment_attempt_id: int
    amount_cents: int
    currency: str
    attempt_number: int
    decline_code: str | None
    decline_class: str | None
    attempted_at: str


class CustomerHistoryOut(BaseModel):
    customer_id: int
    plan_tier: str
    tenure_days: float
    prior_successful_attempts: int
    prior_failed_attempts: int
    prior_recovery_rate: float
    prior_recovery_actions: int


class FailureAnalysisOut(BaseModel):
    decline_code: str
    decline_class: str
    explanation: str
    relevant_actions: list[str]


class RecoveryProbabilityOut(BaseModel):
    is_available: bool
    recovery_probability: float | None = None
    confidence_band: str | None = None
    model_version: str | None = None


class RetryEligibilityOut(BaseModel):
    retry_allowed: bool
    reason_code: str
    message: str
    retry_after: str | None = None


class EligibilityItem(BaseModel):
    action_type: str
    allowed: bool
    reason_code: str
    message: str


class RecoveryPolicyOut(BaseModel):
    policy_version: str
    max_retry_attempts: int
    retry_cooldown_hours: int
    automated_actions_enabled: bool
    eligibilities: list[EligibilityItem]


class CaseStateOut(BaseModel):
    case_id: int
    status: str
    amount_at_risk_cents: int
    amount_recovered_cents: int
    opened_at: str
    resolved_at: str | None
    resolution_reason: str | None
    prior_actions_count: int


class ExpectedRecoveryValueOut(BaseModel):
    expected_values_cents: dict[str, int]


class RecoveryMessageInput(BaseModel):
    channel: str = "email"


class RecoveryMessageOut(BaseModel):
    channel: str
    message: str
    logged: bool


class AuditNoteInput(BaseModel):
    note: str = Field(max_length=500)


class AuditNoteOut(BaseModel):
    recorded: bool


# ------------------------------------------------------------- read tools --


def get_transaction(ctx: ToolContext, _: EmptyInput) -> TransactionOut:
    attempt = case_query.latest_diagnosed_attempt(ctx.db, ctx.case.id)
    if attempt is None:
        raise ToolError("no_diagnosed_attempt", "This case has no diagnosed payment attempt yet.")
    return TransactionOut(
        invoice_id=attempt.invoice_id,
        payment_attempt_id=attempt.id,
        amount_cents=attempt.amount_cents,
        currency=attempt.currency,
        attempt_number=attempt.attempt_number,
        decline_code=attempt.decline_code.value if attempt.decline_code else None,
        decline_class=attempt.decline_class.value if attempt.decline_class else None,
        attempted_at=as_utc(attempt.attempted_at).isoformat(),
    )


def get_customer_history(ctx: ToolContext, _: EmptyInput) -> CustomerHistoryOut:
    customer = ctx.db.get(Customer, ctx.case.customer_id)
    if customer is None:
        raise ToolError("customer_not_found", "The customer for this case could not be found.")
    attempt = case_query.latest_diagnosed_attempt(ctx.db, ctx.case.id)
    now = as_utc(attempt.attempted_at) if attempt else as_utc(customer.created_at)

    prior_success, prior_fail, _ = case_query.prior_attempt_stats(ctx.db, customer.id, now)
    prior_recovery_actions = case_query.prior_recovery_action_count(ctx.db, customer.id, now)
    total = prior_success + prior_fail
    rate = prior_success / total if total > 0 else 0.5
    tenure_days = max(0.0, (now - as_utc(customer.created_at)).total_seconds() / 86400.0)

    return CustomerHistoryOut(
        customer_id=customer.id,
        plan_tier=customer.plan_tier,
        tenure_days=tenure_days,
        prior_successful_attempts=prior_success,
        prior_failed_attempts=prior_fail,
        prior_recovery_rate=rate,
        prior_recovery_actions=prior_recovery_actions,
    )


def analyze_payment_failure(ctx: ToolContext, _: EmptyInput) -> FailureAnalysisOut:
    attempt = case_query.latest_diagnosed_attempt(ctx.db, ctx.case.id)
    if attempt is None or attempt.decline_code is None:
        raise ToolError("no_diagnosed_attempt", "This case has no diagnosed decline to analyze.")
    diag = diagnose(attempt.decline_code)
    return FailureAnalysisOut(
        decline_code=diag.decline_code.value,
        decline_class=diag.decline_class.value,
        explanation=diag.explanation,
        relevant_actions=[a.value for a in diag.relevant_actions],
    )


def calculate_recovery_probability(ctx: ToolContext, _: EmptyInput) -> RecoveryProbabilityOut:
    prediction = case_query.latest_ml_prediction(ctx.db, ctx.case.id)
    if prediction is None:
        return RecoveryProbabilityOut(is_available=False)
    from app.models.ml import ModelVersion

    model_version = ctx.db.get(ModelVersion, prediction.model_version_id)
    return RecoveryProbabilityOut(
        is_available=True,
        recovery_probability=prediction.recovery_probability,
        confidence_band=prediction.confidence_band,
        model_version=model_version.version if model_version else None,
    )


def check_retry_eligibility(ctx: ToolContext, _: EmptyInput) -> RetryEligibilityOut:
    from app.domain.enums import ActionType

    attempt = case_query.latest_diagnosed_attempt(ctx.db, ctx.case.id)
    if attempt is None or attempt.decline_code is None:
        raise ToolError("no_diagnosed_attempt", "This case has no diagnosed decline to evaluate.")
    diag = diagnose(attempt.decline_code)
    result = policy_service.evaluate_for_case(ctx.db, case=ctx.case, diagnosis=diag)
    e = result.eligibility_for(ActionType.RETRY_PAYMENT)
    if e is None:
        raise ToolError("unknown_action", "retry_payment is not a recognized action type.")
    return RetryEligibilityOut(
        retry_allowed=e.allowed,
        reason_code=e.reason_code.value,
        message=e.message,
        retry_after=e.retry_after.isoformat() if e.retry_after else None,
    )


def get_recovery_policy(ctx: ToolContext, _: EmptyInput) -> RecoveryPolicyOut:
    settings = get_settings()
    attempt = case_query.latest_diagnosed_attempt(ctx.db, ctx.case.id)
    if attempt is None or attempt.decline_code is None:
        raise ToolError("no_diagnosed_attempt", "This case has no diagnosed decline to evaluate policy against.")
    diag = diagnose(attempt.decline_code)
    result = policy_service.evaluate_for_case(ctx.db, case=ctx.case, diagnosis=diag)
    return RecoveryPolicyOut(
        policy_version=result.policy_version,
        max_retry_attempts=settings.max_retry_attempts,
        retry_cooldown_hours=settings.retry_cooldown_hours,
        automated_actions_enabled=result.automated_actions_enabled,
        eligibilities=[
            EligibilityItem(
                action_type=e.action_type.value, allowed=e.allowed, reason_code=e.reason_code.value, message=e.message
            )
            for e in result.eligibilities
        ],
    )


def get_case_state(ctx: ToolContext, _: EmptyInput) -> CaseStateOut:
    case = ctx.case
    prior_actions = case_query.list_actions_for_case(ctx.db, case.id)
    return CaseStateOut(
        case_id=case.id,
        status=case.status.value,
        amount_at_risk_cents=case.amount_at_risk_cents,
        amount_recovered_cents=case.amount_recovered_cents,
        opened_at=as_utc(case.opened_at).isoformat(),
        resolved_at=as_utc(case.resolved_at).isoformat() if case.resolved_at else None,
        resolution_reason=case.resolution_reason,
        prior_actions_count=len(prior_actions),
    )


def calculate_expected_recovery_value(ctx: ToolContext, _: EmptyInput) -> ExpectedRecoveryValueOut:
    settings = get_settings()
    attempt = case_query.latest_diagnosed_attempt(ctx.db, ctx.case.id)
    if attempt is None or attempt.decline_code is None:
        raise ToolError("no_diagnosed_attempt", "This case has no diagnosed decline to value.")
    diag = diagnose(attempt.decline_code)
    policy_result = policy_service.evaluate_for_case(ctx.db, case=ctx.case, diagnosis=diag)
    prediction = case_query.latest_ml_prediction(ctx.db, ctx.case.id)
    probability = prediction.recovery_probability if prediction else 0.0

    values = prediction_service.compute_expected_values(
        probability=probability,
        amount_cents=ctx.case.amount_at_risk_cents,
        allowed_action_types=[a.value for a in policy_result.allowed_actions],
        action_costs_cents=settings.action_costs_cents,
    )
    return ExpectedRecoveryValueOut(expected_values_cents=values)


# ------------------------------------------------- non-financial write tools --


_MESSAGE_TEMPLATES = {
    "email": "We noticed a recent payment didn't go through. Update your payment details "
    "here to keep your subscription active — it only takes a minute.",
    "sms": "Your recent payment didn't go through. Tap to update your payment method.",
}


def create_recovery_message(ctx: ToolContext, payload: RecoveryMessageInput) -> RecoveryMessageOut:
    message = _MESSAGE_TEMPLATES.get(payload.channel, _MESSAGE_TEMPLATES["email"])
    audit_service.write_event(
        ctx.db,
        case_id=ctx.case.id,
        event_type=CaseEventType.ACTION_OUTCOME_RECORDED,
        summary=f"Recovery message drafted for the {payload.channel} channel.",
        details={"channel": payload.channel, "message": message},
    )
    return RecoveryMessageOut(channel=payload.channel, message=message, logged=True)


def record_audit_event(ctx: ToolContext, payload: AuditNoteInput) -> AuditNoteOut:
    audit_service.write_event(
        ctx.db,
        case_id=ctx.case.id,
        event_type=CaseEventType.AGENT_DECIDED,
        summary=payload.note,
        details={"source": "agent_note"},
    )
    return AuditNoteOut(recorded=True)


# ------------------------------------------------------------------ registry --


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: object
    is_write: bool


READ_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        "get_transaction",
        "Get the transaction (amount, currency, decline reason) for this case's latest diagnosed attempt.",
        EmptyInput,
        TransactionOut,
        get_transaction,
        False,
    ),
    ToolSpec(
        "get_customer_history",
        "Get the customer's tenure, plan tier, and prior payment success/failure history.",
        EmptyInput,
        CustomerHistoryOut,
        get_customer_history,
        False,
    ),
    ToolSpec(
        "analyze_payment_failure",
        "Get the deterministic diagnosis of this case's decline: class, explanation, and which "
        "action types are even conceptually relevant to it.",
        EmptyInput,
        FailureAnalysisOut,
        analyze_payment_failure,
        False,
    ),
    ToolSpec(
        "calculate_recovery_probability",
        "Get the calibrated ML model's most recent recovery-probability estimate for this case, "
        "if one exists.",
        EmptyInput,
        RecoveryProbabilityOut,
        calculate_recovery_probability,
        False,
    ),
    ToolSpec(
        "check_retry_eligibility",
        "Check whether a payment retry is currently policy-eligible for this case, and why.",
        EmptyInput,
        RetryEligibilityOut,
        check_retry_eligibility,
        False,
    ),
    ToolSpec(
        "get_recovery_policy",
        "Get the full current policy evaluation for this case: every action type, whether it's "
        "allowed, and the specific reason.",
        EmptyInput,
        RecoveryPolicyOut,
        get_recovery_policy,
        False,
    ),
    ToolSpec(
        "get_case_state",
        "Get this case's current status, amounts, and how many actions have already been taken.",
        EmptyInput,
        CaseStateOut,
        get_case_state,
        False,
    ),
    ToolSpec(
        "calculate_expected_recovery_value",
        "Get the expected value (probability x amount - configured cost) of each currently "
        "policy-allowed action.",
        EmptyInput,
        ExpectedRecoveryValueOut,
        calculate_expected_recovery_value,
        False,
    ),
]

WRITE_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        "create_recovery_message",
        "Draft and log a customer-facing recovery message for a channel (email or sms). "
        "Does not move money or change case status.",
        RecoveryMessageInput,
        RecoveryMessageOut,
        create_recovery_message,
        True,
    ),
    ToolSpec(
        "record_audit_event",
        "Record a free-text audit note against this case.",
        AuditNoteInput,
        AuditNoteOut,
        record_audit_event,
        True,
    ),
]

TOOL_REGISTRY: dict[str, ToolSpec] = {spec.name: spec for spec in READ_TOOL_SPECS + WRITE_TOOL_SPECS}


def call_tool(ctx: ToolContext, tool_name: str, raw_input: dict) -> BaseModel:
    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        raise ToolError("unknown_tool", f"'{tool_name}' is not a recognized tool.")
    try:
        parsed_input = spec.input_model.model_validate(raw_input or {})
    except Exception as exc:  # noqa: BLE001 - surfaced as a structured ToolError, not a 500
        raise ToolError("invalid_input", f"Invalid input for {tool_name}: {exc}") from exc
    return spec.handler(ctx, parsed_input)
