import math
from datetime import datetime, timezone

import pytest

from app.domain.enums import DeclineCode
from app.ml.features import RawFeatureInputs, compute_features
from app.ml.schema import ALL_FEATURES


def _inputs(**overrides) -> RawFeatureInputs:
    defaults = dict(
        amount_cents=4900,
        currency="usd",
        decline_code=DeclineCode.CARD_DECLINED,
        payment_method_brand="visa",
        payment_method_age_days=300.0,
        customer_tenure_days=400.0,
        customer_plan_tier="standard",
        customer_prior_successful_attempts=3,
        customer_prior_failed_attempts=1,
        customer_prior_recovery_actions=2,
        customer_avg_historical_amount_cents=4500.0,
        retry_number=0,
        hours_since_last_attempt=48.0,
        invoice_age_days=1.0,
        gateway="sim_gateway_a",
        attempted_at=datetime(2026, 1, 15, 14, 30, tzinfo=timezone.utc),  # Thursday
    )
    defaults.update(overrides)
    return RawFeatureInputs(**defaults)


def test_output_matches_the_declared_feature_schema_exactly():
    row = compute_features(_inputs())
    assert set(row.keys()) == set(ALL_FEATURES)


def test_log_amount_is_log1p_of_amount():
    row = compute_features(_inputs(amount_cents=9999))
    assert row["log_amount"] == pytest.approx(math.log1p(9999))


def test_no_prior_history_gives_a_neutral_recovery_rate():
    row = compute_features(_inputs(customer_prior_successful_attempts=0, customer_prior_failed_attempts=0))
    assert row["customer_prior_recovery_rate"] == 0.5


def test_recovery_rate_reflects_prior_success_and_failure_counts():
    row = compute_features(_inputs(customer_prior_successful_attempts=3, customer_prior_failed_attempts=1))
    assert row["customer_prior_recovery_rate"] == pytest.approx(0.75)


def test_cyclical_encodings_are_bounded():
    row = compute_features(_inputs())
    for key in ("hour_of_day_sin", "hour_of_day_cos", "day_of_week_sin", "day_of_week_cos"):
        assert -1.0 <= row[key] <= 1.0


def test_midnight_and_noon_produce_different_hour_encodings():
    midnight = compute_features(_inputs(attempted_at=datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)))
    noon = compute_features(_inputs(attempted_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)))
    assert midnight["hour_of_day_sin"] != noon["hour_of_day_sin"]


def test_retry_eligible_false_for_expired_card():
    row = compute_features(_inputs(decline_code=DeclineCode.EXPIRED_CARD))
    assert row["retry_eligible"] == 0.0


def test_retry_eligible_true_for_processor_error():
    row = compute_features(_inputs(decline_code=DeclineCode.PROCESSOR_ERROR))
    assert row["retry_eligible"] == 1.0


def test_fraud_signal_only_true_for_fraud_suspected():
    fraud = compute_features(_inputs(decline_code=DeclineCode.FRAUD_SUSPECTED))
    non_fraud = compute_features(_inputs(decline_code=DeclineCode.DO_NOT_HONOR))
    assert fraud["fraud_signal"] == 1.0
    assert non_fraud["fraud_signal"] == 0.0


def test_decline_class_is_derived_from_decline_code_not_passed_in():
    row = compute_features(_inputs(decline_code=DeclineCode.INVALID_METHOD))
    assert row["decline_class"] == "hard"


def test_categorical_fields_pass_through_as_strings():
    row = compute_features(_inputs(payment_method_brand="amex", customer_plan_tier="enterprise", currency="eur"))
    assert row["payment_method_brand"] == "amex"
    assert row["customer_plan_tier"] == "enterprise"
    assert row["currency"] == "eur"
