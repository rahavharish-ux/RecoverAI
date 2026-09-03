from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_payment_gateway
from app.api.serializers import agent_decision_to_schema, agent_execute_to_schema, ingest_result_to_schema
from app.db.session import get_db
from app.integrations.payment_gateway import PaymentGatewayPort
from app.schemas.demo import DemoScenarioRunResult
from app.services import demo_service

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/scenarios/{scenario_id}/run", response_model=DemoScenarioRunResult, status_code=201)
def run_demo_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    gateway: PaymentGatewayPort = Depends(get_payment_gateway),
) -> DemoScenarioRunResult:
    """Runs one Demo Center scenario end to end — DETECT through ACT and
    AUDIT — against a freshly created, fully isolated synthetic
    transaction, so repeated demo runs never reuse (and can never be
    blocked by) an earlier run's case. See app/services/demo_service.py
    for the full architecture note on how Scenario A demonstrates a
    reliable successful recovery without weakening or touching the real
    payment simulator used everywhere else."""
    normalized = scenario_id.upper()
    if normalized not in demo_service.DEMO_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown demo scenario '{scenario_id}'.")

    result = demo_service.run_scenario(db, normalized, gateway=gateway)

    execute_out = None
    if result.execute is not None:
        updated, action, outcome, resulting_attempt, deduplicated = result.execute
        execute_out = agent_execute_to_schema(
            db,
            agent_decision=updated,
            action=action,
            outcome=outcome,
            resulting_attempt=resulting_attempt,
            deduplicated=deduplicated,
        )

    return DemoScenarioRunResult(
        scenario_id=result.scenario_id,
        ingest=ingest_result_to_schema(db, result.ingest),
        decision=agent_decision_to_schema(db, result.decision),
        execute=execute_out,
        second_decision=agent_decision_to_schema(db, result.second_decision) if result.second_decision else None,
        demo_fixture_applied=result.demo_fixture_applied,
    )
