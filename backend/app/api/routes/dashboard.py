from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard import (
    DashboardSummaryOut,
    DecisionSummaryOut,
    EconomicsOut,
    FailureCategoryOut,
    FunnelStageOut,
    PriorityCaseOut,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def summary(db: Session = Depends(get_db)) -> DashboardSummaryOut:
    """Top-line KPIs, computed live from current case/attempt/decision state."""
    return DashboardSummaryOut(**dashboard_service.get_summary(db).__dict__)


@router.get("/funnel", response_model=list[FunnelStageOut])
def funnel(db: Session = Depends(get_db)) -> list[FunnelStageOut]:
    """Detect -> Recovered, as counts of distinct cases that reached each
    stage at least once, with each stage's share of the failed-payment base."""
    return [FunnelStageOut(**s.__dict__) for s in dashboard_service.get_funnel(db)]


@router.get("/failures", response_model=list[FailureCategoryOut])
def failures(db: Session = Depends(get_db)) -> list[FailureCategoryOut]:
    """Cases grouped by their originating decline code, ranked by amount
    involved. retry_eligible is a static taxonomy fact (app/domain/decline_taxonomy.py),
    not derived from outcomes."""
    return [FailureCategoryOut(**c.__dict__) for c in dashboard_service.get_failure_categories(db)]


@router.get("/decisions", response_model=list[DecisionSummaryOut])
def decisions(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[DecisionSummaryOut]:
    """The most recent agent decisions across all cases — the same
    agent_mode/mode_label distinction the Case Intelligence view uses,
    never conflating deterministic and LLM output."""
    return [DecisionSummaryOut(**d.__dict__) for d in dashboard_service.get_recent_decisions(db, limit=limit)]


@router.get("/priority-cases", response_model=list[PriorityCaseOut])
def priority_cases(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[PriorityCaseOut]:
    """Open cases ranked by amount at risk (deterministic, matches the
    ordering GET /cases already uses), enriched with each case's latest
    prediction and decision if one exists."""
    return [PriorityCaseOut(**c.__dict__) for c in dashboard_service.get_priority_cases(db, limit=limit)]


@router.get("/economics", response_model=EconomicsOut)
def economics(db: Session = Depends(get_db)) -> EconomicsOut:
    """Sandbox recovery economics — see EconomicsOut.note for the honesty
    disclaimer attached to every response."""
    return EconomicsOut(**dashboard_service.get_economics(db).__dict__)
