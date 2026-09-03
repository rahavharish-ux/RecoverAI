"""The one function that turns raw, already-known-at-diagnosis-time inputs
into a model-ready feature row. Both the synthetic training generator
(training/synthetic_data.py) and the live prediction service
(app/services/prediction_service.py) call this exact function — there is no
second, parallel feature-construction implementation to drift out of sync
with the first.

Pure and deterministic: no I/O, no randomness, no database access. Every
input here is something that was true *before* any retry was attempted —
none of it is derived from a retry's outcome.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from app.domain.decline_taxonomy import diagnose
from app.domain.enums import ActionType, DeclineClass, DeclineCode
from app.ml.schema import ALL_FEATURES


@dataclass(frozen=True)
class RawFeatureInputs:
    amount_cents: int
    currency: str
    decline_code: DeclineCode
    payment_method_brand: str
    payment_method_age_days: float
    customer_tenure_days: float
    customer_plan_tier: str
    customer_prior_successful_attempts: int
    customer_prior_failed_attempts: int
    customer_prior_recovery_actions: int
    customer_avg_historical_amount_cents: float
    retry_number: int
    hours_since_last_attempt: float
    invoice_age_days: float
    gateway: str
    attempted_at: datetime


def compute_features(inputs: RawFeatureInputs) -> dict:
    diag = diagnose(inputs.decline_code)
    total_prior = inputs.customer_prior_successful_attempts + inputs.customer_prior_failed_attempts
    # No prior history is genuinely uninformative, not "bad" — a neutral
    # 0.5 prior avoids implicitly telling the model "no history = risky".
    prior_recovery_rate = (
        inputs.customer_prior_successful_attempts / total_prior if total_prior > 0 else 0.5
    )
    txn_frequency_per_month = total_prior / max(inputs.customer_tenure_days / 30.0, 1.0)
    hour = inputs.attempted_at.hour
    dow = inputs.attempted_at.weekday()

    row = {
        "amount_cents": float(inputs.amount_cents),
        "log_amount": math.log1p(inputs.amount_cents),
        "payment_method_age_days": float(inputs.payment_method_age_days),
        "customer_tenure_days": float(inputs.customer_tenure_days),
        "customer_prior_successful_attempts": float(inputs.customer_prior_successful_attempts),
        "customer_prior_failed_attempts": float(inputs.customer_prior_failed_attempts),
        "customer_prior_recovery_rate": prior_recovery_rate,
        "customer_prior_recovery_actions": float(inputs.customer_prior_recovery_actions),
        "retry_number": float(inputs.retry_number),
        "hours_since_last_attempt": float(inputs.hours_since_last_attempt),
        "invoice_age_days": float(inputs.invoice_age_days),
        "customer_txn_frequency_per_month": txn_frequency_per_month,
        "customer_avg_historical_amount_cents": float(inputs.customer_avg_historical_amount_cents),
        "hour_of_day_sin": math.sin(2 * math.pi * hour / 24),
        "hour_of_day_cos": math.cos(2 * math.pi * hour / 24),
        "day_of_week_sin": math.sin(2 * math.pi * dow / 7),
        "day_of_week_cos": math.cos(2 * math.pi * dow / 7),
        "retry_eligible": 1.0 if ActionType.RETRY_PAYMENT in diag.relevant_actions else 0.0,
        "fraud_signal": 1.0 if diag.decline_class == DeclineClass.FRAUD else 0.0,
        "currency": inputs.currency,
        "decline_code": diag.decline_code.value,
        "decline_class": diag.decline_class.value,
        "payment_method_brand": inputs.payment_method_brand,
        "customer_plan_tier": inputs.customer_plan_tier,
        "gateway": inputs.gateway,
    }

    assert set(row.keys()) == set(ALL_FEATURES), "feature row drifted from the declared schema"
    return row
