from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_payment_gateway
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.decline_taxonomy import diagnose
from app.domain.enums import CaseEventType, CaseStatus
from app.integrations.payment_gateway import PaymentGatewayPort
from app.models.actions import Action
from app.models.cases import Case
from app.models.ml import MLPrediction, ModelVersion
from app.models.payments import PaymentAttempt
from app.schemas.action import ActionOut, ActionOutcomeOut, ActionRequestIn, ActionResult
from app.schemas.case import CaseEventOut, CaseSummaryOut
from app.schemas.ml import FeatureContributionOut, ModelVersionOut, PredictionOut
from app.schemas.payment_attempt import PaymentAttemptOut
from app.schemas.policy import ActionEligibilityOut, PolicyDecisionOut
from app.services import action_service, audit_service, policy_service, prediction_service
from app.services.action_service import ActionNotEligible

router = APIRouter(prefix="/cases", tags=["cases"])


def _get_case_or_404(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return case


def _latest_diagnosed_attempt(db: Session, case_id: int) -> PaymentAttempt | None:
    return (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.case_id == case_id, PaymentAttempt.decline_code.isnot(None))
        .order_by(PaymentAttempt.attempted_at.desc())
        .first()
    )


@router.get("", response_model=list[CaseSummaryOut])
def list_cases(
    status: CaseStatus | None = Query(default=None, description="Filter by case status."),
    db: Session = Depends(get_db),
) -> list[CaseSummaryOut]:
    """The triage queue: what transactions are affected, ranked by revenue at risk."""
    query = db.query(Case)
    if status is not None:
        query = query.filter(Case.status == status)
    cases = query.order_by(Case.amount_at_risk_cents.desc(), Case.opened_at.asc()).all()
    return [CaseSummaryOut.model_validate(c) for c in cases]


@router.get("/{case_id}", response_model=CaseSummaryOut)
def get_case(case_id: int, db: Session = Depends(get_db)) -> CaseSummaryOut:
    return CaseSummaryOut.model_validate(_get_case_or_404(db, case_id))


@router.get("/{case_id}/events", response_model=list[CaseEventOut])
def get_case_events(case_id: int, db: Session = Depends(get_db)) -> list[CaseEventOut]:
    """The full audit trail: what was recorded, in order, from Detect onward."""
    _get_case_or_404(db, case_id)
    events = audit_service.list_events(db, case_id)
    return [CaseEventOut.model_validate(e) for e in events]


@router.get("/{case_id}/eligibility", response_model=PolicyDecisionOut)
def get_case_eligibility(case_id: int, db: Session = Depends(get_db)) -> PolicyDecisionOut:
    """A fresh policy read against current state: which actions are allowed
    or prohibited right now, and why — re-evaluated, not cached."""
    case = _get_case_or_404(db, case_id)
    latest_attempt = _latest_diagnosed_attempt(db, case_id)
    if latest_attempt is None or latest_attempt.decline_code is None:
        raise HTTPException(
            status_code=409, detail="This case has no diagnosed decline to evaluate eligibility for."
        )
    diag = diagnose(latest_attempt.decline_code)
    result = policy_service.evaluate_for_case(db, case=case, diagnosis=diag)
    return PolicyDecisionOut(
        policy_version=result.policy_version,
        evaluated_at=result.evaluated_at,
        automated_actions_enabled=result.automated_actions_enabled,
        eligibilities=[
            ActionEligibilityOut(
                action_type=e.action_type,
                allowed=e.allowed,
                reason_code=e.reason_code,
                message=e.message,
                retry_after=e.retry_after,
            )
            for e in result.eligibilities
        ],
    )


def _prediction_to_out(db: Session, case: Case, ml_prediction: MLPrediction) -> PredictionOut:
    model_version = db.get(ModelVersion, ml_prediction.model_version_id)
    settings = get_settings()

    expected_values: dict[str, int] = {}
    latest_attempt = _latest_diagnosed_attempt(db, case.id)
    if latest_attempt is not None and latest_attempt.decline_code is not None and case.status == CaseStatus.OPEN:
        diag = diagnose(latest_attempt.decline_code)
        policy_result = policy_service.evaluate_for_case(db, case=case, diagnosis=diag)
        expected_values = prediction_service.compute_expected_values(
            probability=ml_prediction.recovery_probability,
            amount_cents=case.amount_at_risk_cents,
            allowed_action_types=[a.value for a in policy_result.allowed_actions],
            action_costs_cents=settings.action_costs_cents,
        )

    return PredictionOut(
        id=ml_prediction.id,
        case_id=ml_prediction.case_id,
        payment_attempt_id=ml_prediction.payment_attempt_id,
        recovery_probability=ml_prediction.recovery_probability,
        confidence_band=ml_prediction.confidence_band,
        predicted_at=ml_prediction.predicted_at,
        model_version=ModelVersionOut.model_validate(model_version),
        top_contributions=[FeatureContributionOut(**c) for c in ml_prediction.top_contributions],
        expected_values_cents=expected_values,
    )


@router.get("/{case_id}/prediction", response_model=PredictionOut)
def get_case_prediction(case_id: int, db: Session = Depends(get_db)) -> PredictionOut:
    """The most recent PREDICT-stage read for this case: recovery
    probability, confidence band, and the features that drove it — paired
    with the expected value of each currently policy-allowed action."""
    case = _get_case_or_404(db, case_id)
    latest = (
        db.query(MLPrediction)
        .filter(MLPrediction.case_id == case_id)
        .order_by(MLPrediction.predicted_at.desc())
        .first()
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="No prediction has been made for this case yet.")
    return _prediction_to_out(db, case, latest)


@router.post("/{case_id}/predict", response_model=PredictionOut, status_code=201)
def refresh_case_prediction(case_id: int, db: Session = Depends(get_db)) -> PredictionOut:
    """Recompute a prediction for this case against current state — e.g.
    because a model was trained after the case was first diagnosed. Never
    executes anything; purely advisory, exactly like the automatic PREDICT
    step in the ingestion pipeline."""
    case = _get_case_or_404(db, case_id)
    latest_attempt = _latest_diagnosed_attempt(db, case_id)
    if latest_attempt is None or latest_attempt.decline_code is None:
        raise HTTPException(status_code=409, detail="This case has no diagnosed decline to score.")

    diag = diagnose(latest_attempt.decline_code)
    result = prediction_service.predict_recovery_probability(db, case=case, attempt=latest_attempt, diagnosis=diag)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="No active model is available. Run `python -m training.train` from backend/ to train one.",
        )

    audit_service.write_event(
        db,
        case_id=case.id,
        event_type=CaseEventType.PREDICTED,
        summary=f"Estimated retry-success probability: {result.ml_prediction.recovery_probability:.0%} "
        f"({result.ml_prediction.confidence_band} confidence) — recomputed on request.",
        details={"model_version_id": result.model_version.id, "algorithm": result.model_version.algorithm},
        payment_attempt_id=latest_attempt.id,
        ml_prediction_id=result.ml_prediction.id,
    )
    db.commit()

    return _prediction_to_out(db, case, result.ml_prediction)


@router.get("/{case_id}/actions", response_model=list[ActionOut])
def list_case_actions(case_id: int, db: Session = Depends(get_db)) -> list[ActionOut]:
    """Has this case already been acted upon? The full action history."""
    _get_case_or_404(db, case_id)
    actions = (
        db.query(Action).filter(Action.case_id == case_id).order_by(Action.requested_at.asc()).all()
    )
    return [ActionOut.model_validate(a) for a in actions]


@router.post("/{case_id}/actions", response_model=ActionResult, status_code=201)
def post_case_action(
    case_id: int,
    payload: ActionRequestIn,
    db: Session = Depends(get_db),
    gateway: PaymentGatewayPort = Depends(get_payment_gateway),
) -> ActionResult:
    """Act: request execution of a recovery action. Eligibility is
    re-validated server-side regardless of what the caller believes is
    allowed, and the request is idempotent (see services/action_service.py)."""
    case = _get_case_or_404(db, case_id)
    try:
        action, outcome, resulting_attempt, deduplicated = action_service.request_action(
            db,
            case=case,
            action_type=payload.action_type,
            gateway=gateway,
            client_request_id=payload.client_request_id,
        )
    except ActionNotEligible as exc:
        raise HTTPException(
            status_code=422, detail={"reason_code": exc.reason_code, "message": exc.message}
        ) from exc

    db.refresh(case)
    return ActionResult(
        action=ActionOut.model_validate(action),
        outcome=ActionOutcomeOut.model_validate(outcome) if outcome else None,
        resulting_payment_attempt=PaymentAttemptOut.model_validate(resulting_attempt) if resulting_attempt else None,
        case=CaseSummaryOut.model_validate(case),
        deduplicated=deduplicated,
    )
