"""Demo Center orchestration — runs one guided scenario end to end
(DETECT -> DIAGNOSE -> PREDICT -> DECIDE -> ACT -> MEASURE -> AUDIT)
against a freshly created, fully isolated synthetic transaction, so
repeated demo runs can never reuse — and be blocked or poisoned by — an
earlier run's case.

Every stage below calls the exact same real services production traffic
uses (ingestion_service, agent_service, and through it action_service) —
nothing here is scripted or faked. The ONLY demo-specific behavior is an
explicit, clearly labeled fixture at the payment-gateway boundary
(DemoFixtureGatewayAdapter, see app/integrations/payment_gateway.py),
applied ONLY for Scenario A's retry, so that scenario reliably
demonstrates a successful recovery instead of depending on the real
simulator's 0.60 stochastic success rate. Every other scenario, and every
other action within Scenario A itself, runs against the unmodified real
gateway `get_payment_gateway()` already provides to production code.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.domain.enums import AttemptSource, CaseStatus, DecisionStatus, DeclineCode
from app.integrations.payment_gateway import DemoFixtureGatewayAdapter, GatewayResult, PaymentGatewayPort
from app.models.actions import Action, ActionOutcome
from app.models.agent import AgentDecision
from app.models.cases import Case
from app.models.core import Customer, Invoice, PaymentMethod, Subscription
from app.models.payments import PaymentAttempt
from app.services import agent_service, ingestion_service
from app.services.ingestion_service import IngestResult


class UnknownDemoScenario(Exception):
    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        super().__init__(f"Unknown demo scenario '{scenario_id}'.")


@dataclass(frozen=True)
class DemoScenarioProfile:
    scenario_id: str
    decline_code: DeclineCode
    amount_cents: int
    plan_tier: str
    tenure_days: int
    method_age_days: int
    brand: str
    # True ONLY for Scenario A — see DemoFixtureGatewayAdapter above.
    force_retry_success: bool


# Character profiles mirror scripts/seed_demo_data.py's four seeded
# customers so PREDICT-stage features (customer_tenure_days,
# payment_method_age_days, plan_tier) stay realistic — a fresh demo
# customer is *shaped* like a real one, just newly minted per run.
DEMO_SCENARIOS: dict[str, DemoScenarioProfile] = {
    "A": DemoScenarioProfile(
        scenario_id="A",
        decline_code=DeclineCode.PROCESSOR_ERROR,
        amount_cents=2900,
        plan_tier="growth",
        tenure_days=620,
        method_age_days=540,
        brand="visa",
        force_retry_success=True,
    ),
    "B": DemoScenarioProfile(
        scenario_id="B",
        decline_code=DeclineCode.FRAUD_SUSPECTED,
        amount_cents=1900,
        plan_tier="standard",
        tenure_days=45,
        method_age_days=45,
        brand="mastercard",
        force_retry_success=False,
    ),
    "C": DemoScenarioProfile(
        scenario_id="C",
        decline_code=DeclineCode.EXPIRED_CARD,
        amount_cents=4900,
        plan_tier="standard",
        tenure_days=210,
        method_age_days=30,
        brand="visa",
        force_retry_success=False,
    ),
    "D": DemoScenarioProfile(
        scenario_id="D",
        decline_code=DeclineCode.INSUFFICIENT_FUNDS,
        amount_cents=2900,
        plan_tier="growth",
        tenure_days=620,
        method_age_days=540,
        brand="visa",
        force_retry_success=False,
    ),
    "E": DemoScenarioProfile(
        scenario_id="E",
        decline_code=DeclineCode.CARD_DECLINED,
        amount_cents=19900,
        plan_tier="enterprise",
        tenure_days=900,
        method_age_days=880,
        brand="mastercard",
        force_retry_success=False,
    ),
}

ExecuteTuple = tuple[AgentDecision, Action | None, ActionOutcome | None, PaymentAttempt | None, bool]


@dataclass
class DemoScenarioResult:
    scenario_id: str
    ingest: IngestResult
    decision: AgentDecision
    execute: ExecuteTuple | None
    second_decision: AgentDecision | None
    demo_fixture_applied: bool


def _create_demo_fixture(db: Session, profile: DemoScenarioProfile) -> tuple[Invoice, int]:
    """A brand-new, fully isolated synthetic customer/method/subscription/
    invoice for exactly one Demo Center run. Every identifier is unique
    (uuid4-suffixed), so two runs of the same scenario — even back to back
    — never share a case, and one run can never be blocked by state an
    earlier run left behind (e.g. an open case still in cooldown)."""
    now = datetime.now(timezone.utc)
    token = uuid.uuid4().hex[:8]

    customer = Customer(
        name=f"Demo Scenario {profile.scenario_id} ({token})",
        email=f"demo-{profile.scenario_id.lower()}-{token}@recoverai.demo",
        plan_tier=profile.plan_tier,
        created_at=now - timedelta(days=profile.tenure_days),
    )
    db.add(customer)
    db.flush()

    method = PaymentMethod(
        customer_id=customer.id,
        brand=profile.brand,
        last4=f"{int(token[:4], 16) % 10000:04d}",
        exp_month=((now.month + 5) % 12) + 1,
        # A visibly at/near-expiry year for the expired-card scenario is
        # cosmetic realism only — decline_code, not this field, drives the
        # diagnosis and policy outcome.
        exp_year=now.year if profile.decline_code == DeclineCode.EXPIRED_CARD else now.year + 3,
        created_at=now - timedelta(days=profile.method_age_days),
    )
    db.add(method)
    db.flush()

    subscription = Subscription(customer_id=customer.id, plan_tier=profile.plan_tier, status="active")
    db.add(subscription)
    db.flush()

    invoice = Invoice(
        subscription_id=subscription.id,
        customer_id=customer.id,
        amount_cents=profile.amount_cents,
        currency="usd",
        due_date=now + timedelta(days=1),
        status="open",
        created_at=now,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice, method.id


def run_scenario(db: Session, scenario_id: str, *, gateway: PaymentGatewayPort) -> DemoScenarioResult:
    profile = DEMO_SCENARIOS.get(scenario_id)
    if profile is None:
        raise UnknownDemoScenario(scenario_id)

    invoice, payment_method_id = _create_demo_fixture(db, profile)

    # DETECT + DIAGNOSE + PREDICT + (policy) DECIDE — the real ingestion
    # pipeline, identical to what a gateway webhook triggers in production.
    ingest_result = ingestion_service.record_payment_attempt(
        db,
        invoice=invoice,
        payment_method_id=payment_method_id,
        amount_cents=profile.amount_cents,
        currency=invoice.currency,
        decline_code=profile.decline_code,
        source=AttemptSource.EXTERNAL,
    )

    # DECIDE — the real agent service (deterministic engine unless an LLM
    # provider is configured), reasoning only over the policy-filtered set.
    decision = agent_service.decide(db, case=ingest_result.case)

    execute_result: ExecuteTuple | None = None
    demo_fixture_applied = False

    if decision.status == DecisionStatus.AUTO_APPROVED:
        scenario_gateway = gateway
        if profile.force_retry_success:
            scenario_gateway = DemoFixtureGatewayAdapter(
                real_gateway=gateway,
                forced_result=GatewayResult(succeeded=True, decline_code=None, is_simulated=True),
            )
            demo_fixture_applied = True
        # ACT — the real action service, including its own policy
        # re-validation and idempotency guard; nothing here bypasses it.
        execute_result = agent_service.execute(db, agent_decision=decision, gateway=scenario_gateway)

    second_decision: AgentDecision | None = None
    if scenario_id == "D" and execute_result is not None:
        case_after = db.get(Case, ingest_result.case.id)
        if case_after is not None and case_after.status == CaseStatus.OPEN:
            second_decision = agent_service.decide(db, case=case_after)

    return DemoScenarioResult(
        scenario_id=scenario_id,
        ingest=ingest_result,
        decision=decision,
        execute=execute_result,
        second_decision=second_decision,
        demo_fixture_applied=demo_fixture_applied,
    )
