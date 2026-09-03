from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_payment_gateway
from app.db.session import get_db
from app.integrations.payment_gateway import GatewayResult, PaymentGatewayPort
from app.main import app
from app.models import Base
from app.models.core import Customer, Invoice, PaymentMethod, Subscription


class FixedGateway(PaymentGatewayPort):
    """A gateway double with a hardcoded outcome — tests must never depend
    on the real simulator's randomness."""

    def __init__(self, succeed: bool) -> None:
        self.succeed = succeed
        self.calls: list = []

    def retry_charge(self, *, decline_code, amount_cents, currency):
        self.calls.append((decline_code, amount_cents, currency))
        return GatewayResult(succeeded=self.succeed, decline_code=None if self.succeed else decline_code)


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    gateway = FixedGateway(succeed=False)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_payment_gateway] = lambda: gateway

    test_client = TestClient(app)
    test_client.gateway = gateway  # type: ignore[attr-defined]
    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_invoice(session_factory):
    """A single customer/method/subscription/open-invoice, independent of
    any test's own DB session but sharing the same in-memory database."""
    db = session_factory()
    try:
        customer = Customer(name="Test Customer", email="test@example.com", plan_tier="standard")
        db.add(customer)
        db.flush()

        method = PaymentMethod(customer_id=customer.id, brand="visa", last4="4242", exp_month=1, exp_year=2031)
        db.add(method)
        db.flush()

        subscription = Subscription(customer_id=customer.id, plan_tier="standard", status="active")
        db.add(subscription)
        db.flush()

        invoice = Invoice(
            subscription_id=subscription.id,
            customer_id=customer.id,
            amount_cents=4900,
            currency="usd",
            due_date=datetime.now(timezone.utc) + timedelta(days=1),
            status="open",
        )
        db.add(invoice)
        db.commit()

        return {"invoice_id": invoice.id, "payment_method_id": method.id, "customer_id": customer.id}
    finally:
        db.close()
