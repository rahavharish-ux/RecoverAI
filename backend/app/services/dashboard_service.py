"""Read-only aggregation over existing tables — every number here is a
direct query or a documented, deterministic combination of them. Nothing
is estimated from outside the database, nothing is hardcoded, and nothing
here writes anything. This is MEASURE surfaced for humans, not a new
pipeline stage.

All figures are computed over the entire simulated sandbox history (no
date-range filtering — out of scope for this phase) and are meaningful
only relative to each other within this sandbox, never as a claim about
real-world payment recovery.
"""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.domain.decline_taxonomy import diagnose
from app.domain.enums import (
    ActionOutcomeResult,
    ActionStatus,
    ActionType,
    AttemptStatus,
    CaseStatus,
    DeclineCode,
)
from app.models.actions import Action, ActionOutcome
from app.models.agent import AgentDecision
from app.models.cases import Case, PolicyDecision
from app.models.ml import MLPrediction
from app.models.payments import PaymentAttempt

# ------------------------------------------------------------- dataclasses --


@dataclass(frozen=True)
class DashboardSummary:
    revenue_at_risk_cents: int
    recovered_revenue_cents: int
    recovery_rate: float | None  # resolved / (resolved + escalated); None if no terminal cases yet
    active_recovery_cases: int
    failed_payments: int
    human_escalations: int  # decisions that ever required human review, not just cases now escalated


@dataclass(frozen=True)
class FunnelStage:
    stage: str
    case_count: int
    pct_of_failed: float  # 0-100, relative to the failed_payment stage


@dataclass(frozen=True)
class FailureCategory:
    decline_code: str
    decline_class: str
    retry_eligible: bool
    case_count: int
    amount_involved_cents: int
    resolved_count: int
    escalated_count: int
    open_count: int


@dataclass(frozen=True)
class DecisionSummary:
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


@dataclass(frozen=True)
class PriorityCase:
    case_id: int
    amount_at_risk_cents: int
    decline_code: str | None
    recovery_probability: float | None
    expected_value_cents: int | None
    risk_level: str  # "low" | "medium" | "high"
    recommended_action: str | None
    requires_human_review: bool


@dataclass(frozen=True)
class Economics:
    revenue_at_risk_cents: int
    potential_recoverable_cents: int  # sum(probability x amount_at_risk) over open cases with a prediction
    recovered_revenue_cents: int
    recovery_attempts: int
    successful_recoveries: int
    human_escalations: int
    action_cost_cents: int
    net_recovery_value_cents: int


# ---------------------------------------------------------------- helpers --


def _all_cases(db: Session) -> list[Case]:
    return db.query(Case).all()


def _original_amount_cents(case: Case) -> int:
    """A case's amount_at_risk_cents is zeroed on resolution (see
    ingestion_service._resolve_case) — this reconstructs the original
    invoice amount regardless of the case's current status."""
    return case.amount_at_risk_cents if case.status != CaseStatus.RESOLVED else case.amount_recovered_cents


# ----------------------------------------------------------------- summary --


def get_summary(db: Session) -> DashboardSummary:
    cases = _all_cases(db)
    revenue_at_risk = sum(c.amount_at_risk_cents for c in cases if c.status == CaseStatus.OPEN)
    recovered = sum(c.amount_recovered_cents for c in cases)
    resolved_count = sum(1 for c in cases if c.status == CaseStatus.RESOLVED)
    escalated_count = sum(1 for c in cases if c.status == CaseStatus.ESCALATED)
    terminal = resolved_count + escalated_count
    recovery_rate = (resolved_count / terminal) if terminal > 0 else None

    failed_payments = db.query(PaymentAttempt).filter(PaymentAttempt.status == AttemptStatus.FAILED).count()
    human_escalations = db.query(AgentDecision).filter(AgentDecision.requires_human_review.is_(True)).count()

    return DashboardSummary(
        revenue_at_risk_cents=revenue_at_risk,
        recovered_revenue_cents=recovered,
        recovery_rate=recovery_rate,
        active_recovery_cases=sum(1 for c in cases if c.status == CaseStatus.OPEN),
        failed_payments=failed_payments,
        human_escalations=human_escalations,
    )


# ------------------------------------------------------------------ funnel --


def get_funnel(db: Session) -> list[FunnelStage]:
    cases = _all_cases(db)
    total = len(cases)

    diagnosed_case_ids = {
        pa.case_id for pa in db.query(PaymentAttempt.case_id).filter(PaymentAttempt.decline_code.isnot(None)).all()
    }
    predicted_case_ids = {row[0] for row in db.query(MLPrediction.case_id).distinct().all()}

    policy_rows = db.query(PolicyDecision.case_id, PolicyDecision.eligibilities).all()
    policy_eligible_case_ids: set[int] = set()
    for case_id, eligibilities in policy_rows:
        for e in eligibilities:
            if e.get("allowed") and e.get("action_type") in ("retry_payment", "request_method_update"):
                policy_eligible_case_ids.add(case_id)
                break

    decided_case_ids = {row[0] for row in db.query(AgentDecision.case_id).distinct().all()}
    actioned_case_ids = {
        row[0]
        for row in db.query(Action.case_id).filter(Action.status == ActionStatus.EXECUTED).distinct().all()
    }
    recovered_case_ids = {c.id for c in cases if c.status == CaseStatus.RESOLVED}

    def pct(n: int) -> float:
        return round(100.0 * n / total, 1) if total > 0 else 0.0

    stages = [
        ("failed_payment", total),
        ("diagnosed", len(diagnosed_case_ids)),
        ("predicted", len(predicted_case_ids)),
        ("policy_eligible", len(policy_eligible_case_ids)),
        ("agent_decision", len(decided_case_ids)),
        ("recovery_action", len(actioned_case_ids)),
        ("recovered", len(recovered_case_ids)),
    ]
    return [FunnelStage(stage=name, case_count=count, pct_of_failed=pct(count)) for name, count in stages]


# --------------------------------------------------------------- failures --


def get_failure_categories(db: Session) -> list[FailureCategory]:
    cases = _all_cases(db)
    # Each case's decline_code is stable across its lifetime in this
    # simulator (a retry that fails again reuses the same code — see
    # app/integrations/payment_gateway.py) — the first diagnosed attempt on
    # a case is a reliable, cheap way to categorize it.
    first_attempt_by_case: dict[int, PaymentAttempt] = {}
    attempts = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.decline_code.isnot(None))
        .order_by(PaymentAttempt.attempted_at.asc())
        .all()
    )
    for attempt in attempts:
        if attempt.case_id is not None and attempt.case_id not in first_attempt_by_case:
            first_attempt_by_case[attempt.case_id] = attempt

    by_code: dict[DeclineCode, list[Case]] = {}
    for case in cases:
        attempt = first_attempt_by_case.get(case.id)
        if attempt is None or attempt.decline_code is None:
            continue
        by_code.setdefault(attempt.decline_code, []).append(case)

    results: list[FailureCategory] = []
    for code, code_cases in by_code.items():
        diag = diagnose(code)
        results.append(
            FailureCategory(
                decline_code=code.value,
                decline_class=diag.decline_class.value,
                retry_eligible=ActionType.RETRY_PAYMENT in diag.relevant_actions,
                case_count=len(code_cases),
                amount_involved_cents=sum(_original_amount_cents(c) for c in code_cases),
                resolved_count=sum(1 for c in code_cases if c.status == CaseStatus.RESOLVED),
                escalated_count=sum(1 for c in code_cases if c.status == CaseStatus.ESCALATED),
                open_count=sum(1 for c in code_cases if c.status == CaseStatus.OPEN),
            )
        )
    results.sort(key=lambda r: r.amount_involved_cents, reverse=True)
    return results


# --------------------------------------------------------------- decisions --


def get_recent_decisions(db: Session, limit: int = 20) -> list[DecisionSummary]:
    decisions = db.query(AgentDecision).order_by(AgentDecision.decided_at.desc()).limit(limit).all()
    summaries: list[DecisionSummary] = []
    for d in decisions:
        case = db.get(Case, d.case_id)
        attempt = db.get(PaymentAttempt, d.payment_attempt_id) if d.payment_attempt_id else None
        mode_label = "Agentic AI Decision Engine" if d.agent_mode.value == "llm" else "Deterministic Decision Engine"
        expected_value = (
            d.expected_values_cents.get(d.selected_action.value) if d.selected_action and d.expected_values_cents else None
        )
        summaries.append(
            DecisionSummary(
                decision_id=d.id,
                case_id=d.case_id,
                amount_at_risk_cents=case.amount_at_risk_cents if case else 0,
                decline_code=attempt.decline_code.value if attempt and attempt.decline_code else None,
                recovery_probability=d.recovery_probability,
                selected_action=d.selected_action.value if d.selected_action else None,
                expected_value_cents=expected_value,
                agent_mode=d.agent_mode.value,
                mode_label=mode_label,
                risk_flags=d.risk_flags,
                status=d.status.value,
                decided_at=d.decided_at,
            )
        )
    return summaries


# ------------------------------------------------------------ priority queue --


def _risk_level(risk_flags: list[str], probability: float | None) -> str:
    if any(f in risk_flags for f in ("fraud_signal", "high_value_transaction")):
        return "high"
    if probability is not None and probability < 0.4:
        return "medium"
    if risk_flags:
        return "medium"
    return "low"


def get_priority_cases(db: Session, limit: int = 20) -> list[PriorityCase]:
    open_cases = (
        db.query(Case)
        .filter(Case.status == CaseStatus.OPEN)
        .order_by(Case.amount_at_risk_cents.desc())
        .limit(limit)
        .all()
    )
    results: list[PriorityCase] = []
    for case in open_cases:
        prediction = (
            db.query(MLPrediction)
            .filter(MLPrediction.case_id == case.id)
            .order_by(MLPrediction.predicted_at.desc())
            .first()
        )
        decision = (
            db.query(AgentDecision)
            .filter(AgentDecision.case_id == case.id)
            .order_by(AgentDecision.decided_at.desc())
            .first()
        )
        attempt = (
            db.query(PaymentAttempt)
            .filter(PaymentAttempt.case_id == case.id, PaymentAttempt.decline_code.isnot(None))
            .order_by(PaymentAttempt.attempted_at.desc())
            .first()
        )
        probability = prediction.recovery_probability if prediction else None
        risk_flags = decision.risk_flags if decision else []
        expected_value = (
            decision.expected_values_cents.get(decision.selected_action.value)
            if decision and decision.selected_action and decision.expected_values_cents
            else None
        )
        results.append(
            PriorityCase(
                case_id=case.id,
                amount_at_risk_cents=case.amount_at_risk_cents,
                decline_code=attempt.decline_code.value if attempt and attempt.decline_code else None,
                recovery_probability=probability,
                expected_value_cents=expected_value,
                risk_level=_risk_level(risk_flags, probability),
                recommended_action=decision.selected_action.value if decision and decision.selected_action else None,
                requires_human_review=decision.requires_human_review if decision else False,
            )
        )
    return results


# ---------------------------------------------------------------- economics --


def get_economics(db: Session, settings: Settings | None = None) -> Economics:
    settings = settings or get_settings()
    cases = _all_cases(db)

    revenue_at_risk = sum(c.amount_at_risk_cents for c in cases if c.status == CaseStatus.OPEN)
    recovered = sum(c.amount_recovered_cents for c in cases)

    potential_recoverable = 0
    for case in cases:
        if case.status != CaseStatus.OPEN:
            continue
        prediction = (
            db.query(MLPrediction)
            .filter(MLPrediction.case_id == case.id)
            .order_by(MLPrediction.predicted_at.desc())
            .first()
        )
        if prediction is not None:
            potential_recoverable += round(prediction.recovery_probability * case.amount_at_risk_cents)

    executed_actions = db.query(Action).filter(Action.status == ActionStatus.EXECUTED).all()
    recovery_attempts = sum(1 for a in executed_actions if a.action_type == ActionType.RETRY_PAYMENT)
    action_cost_cents = sum(settings.action_costs_cents.get(a.action_type.value, 0) for a in executed_actions)

    successful_recoveries = (
        db.query(ActionOutcome).filter(ActionOutcome.result == ActionOutcomeResult.SUCCEEDED).count()
    )
    human_escalations = db.query(AgentDecision).filter(AgentDecision.requires_human_review.is_(True)).count()

    return Economics(
        revenue_at_risk_cents=revenue_at_risk,
        potential_recoverable_cents=potential_recoverable,
        recovered_revenue_cents=recovered,
        recovery_attempts=recovery_attempts,
        successful_recoveries=successful_recoveries,
        human_escalations=human_escalations,
        action_cost_cents=action_cost_cents,
        net_recovery_value_cents=recovered - action_cost_cents,
    )
