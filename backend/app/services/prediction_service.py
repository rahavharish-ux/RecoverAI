"""Assembles live database state into the same feature contract the
training pipeline uses (app/ml/features.py), runs the active model, and
persists the resulting MLPrediction row. This is the PREDICT stage.

Mirrors policy_service.py's shape deliberately: a DB-aware orchestrator
wrapping pure logic. Best-effort and read-only with respect to the rest of
the pipeline — if no model is trained yet, or the diagnosis can't be
featurized, this returns None and the caller (ingestion_service) proceeds
to Decide exactly as it did before PREDICT existed. Nothing here writes to
`cases`, `actions`, or influences `app/domain/policy.py` in any way; DECIDE
remains entirely deterministic and entirely unaware this module exists.
"""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.core.timeutil import as_utc
from app.domain.decline_taxonomy import Diagnosis
from app.domain.enums import ActionStatus, AttemptStatus
from app.ml import model_registry
from app.ml.explain import FeatureContribution, explain_prediction
from app.ml.features import RawFeatureInputs, compute_features
from app.ml.schema import ALL_FEATURES, CATEGORICAL_FEATURES, NO_PRIOR_ATTEMPT_HOURS_SENTINEL, confidence_band
from app.models.actions import Action
from app.models.cases import Case
from app.models.core import Customer, Invoice, PaymentMethod
from app.models.ml import MLPrediction, ModelVersion
from app.models.payments import PaymentAttempt

# Phase 1's simulator doesn't yet differentiate simulated gateways per
# attempt (see app/integrations/payment_gateway.py) — the trained model
# still learns from `gateway` since the training data varies it, but a live
# request always supplies this fixed default until payment_attempts grows
# a real gateway column.
DEFAULT_GATEWAY = "sim_gateway_a"


@dataclass(frozen=True)
class PredictionResult:
    ml_prediction: MLPrediction
    model_version: ModelVersion
    contributions: list[FeatureContribution]


def _prior_attempt_stats(db: Session, customer_id: int, before: datetime) -> tuple[int, int, float | None]:
    rows = (
        db.query(PaymentAttempt)
        .join(Invoice, PaymentAttempt.invoice_id == Invoice.id)
        .filter(Invoice.customer_id == customer_id, PaymentAttempt.attempted_at < before)
        .all()
    )
    successes = sum(1 for a in rows if a.status == AttemptStatus.SUCCEEDED)
    failures = sum(1 for a in rows if a.status == AttemptStatus.FAILED)
    avg_amount = (sum(a.amount_cents for a in rows) / len(rows)) if rows else None
    return successes, failures, avg_amount


def _prior_recovery_action_count(db: Session, customer_id: int, before: datetime) -> int:
    return (
        db.query(Action)
        .join(Case, Action.case_id == Case.id)
        .filter(Case.customer_id == customer_id, Action.requested_at < before, Action.status == ActionStatus.EXECUTED)
        .count()
    )


def _case_retry_context(db: Session, case_id: int, before: datetime) -> tuple[int, float]:
    prior = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.case_id == case_id, PaymentAttempt.attempted_at < before)
        .order_by(PaymentAttempt.attempted_at.desc())
        .all()
    )
    if not prior:
        return 0, NO_PRIOR_ATTEMPT_HOURS_SENTINEL
    hours_since_last = max(0.0, (before - as_utc(prior[0].attempted_at)).total_seconds() / 3600.0)
    return len(prior), hours_since_last


def predict_recovery_probability(
    db: Session, *, case: Case, attempt: PaymentAttempt, diagnosis: Diagnosis
) -> PredictionResult | None:
    active = model_registry.get_active_model(db)
    if active is None:
        return None

    customer = db.get(Customer, case.customer_id)
    payment_method = db.get(PaymentMethod, attempt.payment_method_id)
    invoice = db.get(Invoice, attempt.invoice_id)
    if customer is None or payment_method is None or invoice is None:
        return None

    now = as_utc(attempt.attempted_at)
    prior_success, prior_fail, avg_amount = _prior_attempt_stats(db, customer.id, now)
    prior_recovery_actions = _prior_recovery_action_count(db, customer.id, now)
    retry_number, hours_since_last = _case_retry_context(db, case.id, now)

    method_created = as_utc(payment_method.created_at)
    customer_created = as_utc(customer.created_at)
    invoice_created = as_utc(invoice.created_at)

    inputs = RawFeatureInputs(
        amount_cents=attempt.amount_cents,
        currency=attempt.currency,
        decline_code=diagnosis.decline_code,
        payment_method_brand=payment_method.brand,
        payment_method_age_days=max(0.0, (now - method_created).total_seconds() / 86400.0),
        customer_tenure_days=max(0.0, (now - customer_created).total_seconds() / 86400.0),
        customer_plan_tier=customer.plan_tier,
        customer_prior_successful_attempts=prior_success,
        customer_prior_failed_attempts=prior_fail,
        customer_prior_recovery_actions=prior_recovery_actions,
        customer_avg_historical_amount_cents=avg_amount if avg_amount is not None else float(attempt.amount_cents),
        retry_number=float(retry_number),
        hours_since_last_attempt=hours_since_last,
        invoice_age_days=max(0.0, (now - invoice_created).total_seconds() / 86400.0),
        gateway=DEFAULT_GATEWAY,
        attempted_at=now,
    )
    feature_row = compute_features(inputs)

    X = pd.DataFrame([feature_row])[ALL_FEATURES]
    probability = float(active.calibrated_pipeline.predict_proba(X)[0, 1])
    band = confidence_band(probability)

    contributions = explain_prediction(
        explanation_artifacts=active.explanation,
        feature_row=feature_row,
        categorical_features=CATEGORICAL_FEATURES,
    )

    row = MLPrediction(
        case_id=case.id,
        payment_attempt_id=attempt.id,
        model_version_id=active.model_version.id,
        recovery_probability=probability,
        confidence_band=band,
        feature_snapshot=feature_row,
        top_contributions=[c.to_dict() for c in contributions],
    )
    db.add(row)
    db.flush()

    return PredictionResult(ml_prediction=row, model_version=active.model_version, contributions=contributions)


def compute_expected_values(
    *, probability: float, amount_cents: int, allowed_action_types: list[str], action_costs_cents: dict[str, int]
) -> dict[str, int]:
    """expected_value = recovery_probability x recoverable_amount - action_cost,
    for RETRY_PAYMENT only — the only action type the recovery probability
    is actually about. Other allowed action types get their (negative,
    cost-only) value too, so the caller can rank the full allowed set, but
    their value is NOT driven by any ML output — only by configured cost.
    Action costs come from `Settings.action_costs_cents` (deterministic
    configuration), never invented here."""
    values: dict[str, int] = {}
    for action_type in allowed_action_types:
        cost = action_costs_cents.get(action_type, 0)
        if action_type == "retry_payment":
            values[action_type] = round(probability * amount_cents) - cost
        else:
            values[action_type] = -cost
    return values
