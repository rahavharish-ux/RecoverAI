from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_payment_gateway
from app.api.routes.agent import _decide_limiter, _execute_limiter
from app.api.routes.demo import _demo_run_limiter
from app.db.session import get_db
from app.integrations.payment_gateway import GatewayResult, PaymentGatewayPort
from app.main import app
from app.ml.schema import FEATURE_SCHEMA_VERSION
from app.models import Base
from app.models.core import Customer, Invoice, PaymentMethod, Subscription
from app.models.ml import ModelVersion


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
    # The rate limiters guard real (public, scriptable) traffic — the test
    # suite's own request volume isn't the threat they exist for, and a
    # shared in-memory limiter would otherwise trip across unrelated
    # tests sharing this process. See app/core/rate_limit.py.
    app.dependency_overrides[_decide_limiter] = lambda: None
    app.dependency_overrides[_execute_limiter] = lambda: None
    app.dependency_overrides[_demo_run_limiter] = lambda: None

    test_client = TestClient(app)
    test_client.gateway = gateway  # type: ignore[attr-defined]
    yield test_client

    app.dependency_overrides.clear()


class StubPipeline:
    """A trivial stand-in for a trained pipeline, used by the ML API/service
    tests so they exercise the prediction_service <-> model_registry
    integration without paying for a real model fit — training's own
    correctness is covered separately (tests/integration/test_ml_training_pipeline.py)."""

    def predict_proba(self, X):
        probs = []
        for _, row in X.iterrows():
            if row.get("fraud_signal", 0) == 1:
                p = 0.02
            elif row.get("retry_eligible", 0) == 0:
                p = 0.05
            else:
                p = 0.55
            probs.append([1 - p, p])
        return np.array(probs)


@pytest.fixture()
def stub_active_model(session_factory, tmp_path) -> int:
    """Registers a fake-but-structurally-valid active model in the test DB
    and returns its model_version_id."""
    explanation = {
        "kind": "importance",
        "feature_names": ["num__customer_prior_recovery_rate", "cat__decline_code_card_declined"],
        "weights": [0.42, 0.15],
        "numeric_feature_medians": {"customer_prior_recovery_rate": 0.5},
    }
    artifact_path = tmp_path / "stub_model.joblib"
    joblib.dump(
        {
            "calibrated_pipeline": StubPipeline(),
            "algorithm": "stub",
            "operating_threshold": 0.3,
            "explanation": explanation,
        },
        artifact_path,
    )

    db = session_factory()
    try:
        row = ModelVersion(
            model_name="recovery_probability",
            algorithm="stub",
            version="v-test",
            dataset_version="synthetic-v1-seed1-cust10",
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            is_calibrated=True,
            operating_threshold=0.3,
            metrics={"note": "stub metrics for testing", "split": {"train_n": 10, "val_n": 2, "test_n": 2}},
            artifact_path=str(artifact_path),
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


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
