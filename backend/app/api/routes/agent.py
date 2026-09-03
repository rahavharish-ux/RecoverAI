from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_payment_gateway
from app.db.session import get_db
from app.integrations.payment_gateway import PaymentGatewayPort
from app.models.agent import AgentDecision, AgentToolCall
from app.models.cases import Case
from app.schemas.action import ActionOut, ActionOutcomeOut
from app.schemas.agent import (
    AgentDecisionOut,
    AgentExecuteRequest,
    AgentExecuteResult,
    AgentReviewRequest,
    AgentToolCallOut,
    AgentTraceOut,
)
from app.schemas.case import CaseSummaryOut
from app.schemas.payment_attempt import PaymentAttemptOut
from app.services import agent_service
from app.services.action_service import ActionNotEligible
from app.services.agent_service import AgentDecisionNotExecutable

router = APIRouter(prefix="/cases", tags=["agent"])


def _get_case_or_404(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return case


def _get_decision_or_404(db: Session, case_id: int, decision_id: int) -> AgentDecision:
    decision = db.get(AgentDecision, decision_id)
    if decision is None or decision.case_id != case_id:
        raise HTTPException(status_code=404, detail=f"Agent decision {decision_id} not found for case {case_id}.")
    return decision


def _decision_to_out(db: Session, decision: AgentDecision) -> AgentDecisionOut:
    tool_calls = (
        db.query(AgentToolCall)
        .filter(AgentToolCall.agent_decision_id == decision.id)
        .order_by(AgentToolCall.sequence.asc())
        .all()
    )
    out = AgentDecisionOut.model_validate(decision)
    out.tool_calls = [AgentToolCallOut.model_validate(tc) for tc in tool_calls]
    return out


@router.post("/{case_id}/agent/decide", response_model=AgentDecisionOut, status_code=201)
def decide(case_id: int, db: Session = Depends(get_db)) -> AgentDecisionOut:
    """DECIDE: the agent reasons over the case, strictly within the
    policy-allowed action set, and produces a structured decision. This
    never executes anything — see /agent/execute."""
    case = _get_case_or_404(db, case_id)
    decision = agent_service.decide(db, case=case)
    return _decision_to_out(db, decision)


@router.post("/{case_id}/agent/execute", response_model=AgentExecuteResult, status_code=201)
def execute(
    case_id: int,
    payload: AgentExecuteRequest,
    decision_id: int | None = None,
    db: Session = Depends(get_db),
    gateway: PaymentGatewayPort = Depends(get_payment_gateway),
) -> AgentExecuteResult:
    """EXECUTE: re-validates the decision from scratch — current case
    state, current policy, current retry/cooldown limits, idempotency —
    then performs the action through the unmodified Phase 1 action
    service. A decision that requires human review cannot be executed
    directly here; see the /approve endpoint."""
    case = _get_case_or_404(db, case_id)
    decision = (
        _get_decision_or_404(db, case_id, decision_id)
        if decision_id is not None
        else db.query(AgentDecision)
        .filter(AgentDecision.case_id == case_id)
        .order_by(AgentDecision.decided_at.desc())
        .first()
    )
    if decision is None:
        raise HTTPException(status_code=404, detail="No agent decision exists for this case yet.")

    try:
        updated, action, outcome, resulting_attempt, deduplicated = agent_service.execute(
            db, agent_decision=decision, gateway=gateway, client_request_id=payload.client_request_id
        )
    except AgentDecisionNotExecutable as exc:
        raise HTTPException(status_code=409, detail={"reason_code": exc.code, "message": exc.message}) from exc
    except ActionNotEligible as exc:
        raise HTTPException(status_code=422, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc

    db.refresh(case)
    return AgentExecuteResult(
        agent_decision=_decision_to_out(db, updated),
        action=ActionOut.model_validate(action) if action else None,
        outcome=ActionOutcomeOut.model_validate(outcome) if outcome else None,
        resulting_payment_attempt=PaymentAttemptOut.model_validate(resulting_attempt) if resulting_attempt else None,
        case=CaseSummaryOut.model_validate(case),
        deduplicated=deduplicated,
    )


@router.post("/{case_id}/agent/decisions/{decision_id}/approve", response_model=AgentExecuteResult)
def approve(
    case_id: int,
    decision_id: int,
    payload: AgentReviewRequest,
    db: Session = Depends(get_db),
    gateway: PaymentGatewayPort = Depends(get_payment_gateway),
) -> AgentExecuteResult:
    """A human approves a HUMAN_REVIEW decision — this immediately
    triggers EXECUTE with the same full re-validation."""
    _get_case_or_404(db, case_id)
    decision = _get_decision_or_404(db, case_id, decision_id)
    try:
        updated, action, outcome, resulting_attempt, deduplicated = agent_service.approve_decision(
            db, agent_decision=decision, reviewed_by=payload.reviewed_by, note=payload.note, gateway=gateway
        )
    except AgentDecisionNotExecutable as exc:
        raise HTTPException(status_code=409, detail={"reason_code": exc.code, "message": exc.message}) from exc
    except ActionNotEligible as exc:
        raise HTTPException(status_code=422, detail={"reason_code": exc.reason_code, "message": exc.message}) from exc

    case = db.get(Case, case_id)
    return AgentExecuteResult(
        agent_decision=_decision_to_out(db, updated),
        action=ActionOut.model_validate(action) if action else None,
        outcome=ActionOutcomeOut.model_validate(outcome) if outcome else None,
        resulting_payment_attempt=PaymentAttemptOut.model_validate(resulting_attempt) if resulting_attempt else None,
        case=CaseSummaryOut.model_validate(case),
        deduplicated=deduplicated,
    )


@router.post("/{case_id}/agent/decisions/{decision_id}/reject", response_model=AgentDecisionOut)
def reject(
    case_id: int, decision_id: int, payload: AgentReviewRequest, db: Session = Depends(get_db)
) -> AgentDecisionOut:
    """A human rejects a HUMAN_REVIEW decision — no action is executed."""
    _get_case_or_404(db, case_id)
    decision = _get_decision_or_404(db, case_id, decision_id)
    try:
        updated = agent_service.reject_decision(db, agent_decision=decision, reviewed_by=payload.reviewed_by, note=payload.note)
    except AgentDecisionNotExecutable as exc:
        raise HTTPException(status_code=409, detail={"reason_code": exc.code, "message": exc.message}) from exc
    return _decision_to_out(db, updated)


@router.get("/{case_id}/agent/trace", response_model=AgentTraceOut)
def get_trace(case_id: int, db: Session = Depends(get_db)) -> AgentTraceOut:
    """The full agent trace for a case: every decision ever made, in
    order, each with its own tool-call log — model/provider, reasoning,
    selection, and execution result all in one place."""
    _get_case_or_404(db, case_id)
    decisions = (
        db.query(AgentDecision).filter(AgentDecision.case_id == case_id).order_by(AgentDecision.decided_at.asc()).all()
    )
    return AgentTraceOut(case_id=case_id, decisions=[_decision_to_out(db, d) for d in decisions])


@router.get("/{case_id}/decision", response_model=AgentDecisionOut)
def get_latest_decision(case_id: int, db: Session = Depends(get_db)) -> AgentDecisionOut:
    """Convenience read: the most recent agent decision for this case."""
    _get_case_or_404(db, case_id)
    decision = (
        db.query(AgentDecision).filter(AgentDecision.case_id == case_id).order_by(AgentDecision.decided_at.desc()).first()
    )
    if decision is None:
        raise HTTPException(status_code=404, detail="No agent decision exists for this case yet.")
    return _decision_to_out(db, decision)
