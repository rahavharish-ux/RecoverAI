"""The feature contract — the single source of truth both the offline
training pipeline (training/synthetic_data.py, training/train.py) and the
live prediction service (app/services/prediction_service.py) build against.
Changing this file changes what a trained model expects; bump
FEATURE_SCHEMA_VERSION whenever a feature is added, removed, or redefined
so a persisted prediction can always be traced back to the schema that
produced it.
"""

FEATURE_SCHEMA_VERSION = "features-v1"

# Numeric / already-encoded-boolean features, in a fixed order the
# ColumnTransformer relies on.
NUMERIC_FEATURES = [
    "amount_cents",
    "log_amount",
    "payment_method_age_days",
    "customer_tenure_days",
    "customer_prior_successful_attempts",
    "customer_prior_failed_attempts",
    "customer_prior_recovery_rate",
    "customer_prior_recovery_actions",
    "retry_number",
    "hours_since_last_attempt",
    "invoice_age_days",
    "customer_txn_frequency_per_month",
    "customer_avg_historical_amount_cents",
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "retry_eligible",
    "fraud_signal",
]

CATEGORICAL_FEATURES = [
    "currency",
    "decline_code",
    "decline_class",
    "payment_method_brand",
    "customer_plan_tier",
    "gateway",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

TARGET_COLUMN = "retry_succeeded"

# Shared between the synthetic generator and the live prediction service:
# the sentinel used for "no prior attempt exists on this case yet" — a
# value distinct from any realistic real gap, rather than a magic number
# defined twice.
NO_PRIOR_ATTEMPT_HOURS_SENTINEL = 999.0

# Fixed, documented cut points on the *calibrated* probability — a
# configured convention for display purposes, not a claim that these are
# the statistically optimal boundaries. See training/train.py for the
# separate, validation-set-driven operating-threshold search.
CONFIDENCE_BAND_THRESHOLDS = {"high": 0.66, "medium": 0.33}


def confidence_band(probability: float) -> str:
    if probability >= CONFIDENCE_BAND_THRESHOLDS["high"]:
        return "high"
    if probability >= CONFIDENCE_BAND_THRESHOLDS["medium"]:
        return "medium"
    return "low"
