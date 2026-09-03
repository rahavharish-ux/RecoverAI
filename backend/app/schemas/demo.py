from pydantic import BaseModel

from app.schemas.agent import AgentDecisionOut, AgentExecuteResult
from app.schemas.payment_attempt import PaymentAttemptIngestResult


class DemoScenarioRunResult(BaseModel):
    """The full, real result of one Demo Center scenario run — everything
    the frontend needs to render the scenario's lifecycle, all of it
    sourced from persisted rows the same way the API's other read
    endpoints are. `execute` is null when the decision requires human
    review (nothing was executed); `second_decision` is populated only for
    Scenario D's cooldown-protection follow-up decide call."""

    scenario_id: str
    ingest: PaymentAttemptIngestResult
    decision: AgentDecisionOut
    execute: AgentExecuteResult | None
    second_decision: AgentDecisionOut | None
    demo_fixture_applied: bool
