import numpy as np
import pandas as pd

from app.domain.enums import ActionType, DeclineClass, DeclineCode
from app.ml.schema import ALL_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN
from training.synthetic_data import GeneratorConfig, generate_dataset

SMALL_CONFIG = GeneratorConfig(n_customers=80, avg_events_per_customer=3.0, seed=7)


def test_generation_is_deterministic_given_the_same_seed():
    a = generate_dataset(SMALL_CONFIG)
    b = generate_dataset(GeneratorConfig(n_customers=80, avg_events_per_customer=3.0, seed=7))
    pd.testing.assert_frame_equal(a, b)


def test_different_seeds_produce_different_data():
    a = generate_dataset(SMALL_CONFIG)
    b = generate_dataset(GeneratorConfig(n_customers=80, avg_events_per_customer=3.0, seed=8))
    assert not a.equals(b)


def test_dataset_version_reflects_generator_parameters():
    assert SMALL_CONFIG.dataset_version == "synthetic-v1-seed7-cust80"


def test_schema_matches_the_declared_feature_contract():
    df = generate_dataset(SMALL_CONFIG)
    assert set(df.columns) == set(ALL_FEATURES) | {TARGET_COLUMN}


def test_no_missing_or_non_finite_values():
    df = generate_dataset(SMALL_CONFIG)
    assert df[NUMERIC_FEATURES].isna().sum().sum() == 0
    assert np.isfinite(df[NUMERIC_FEATURES].to_numpy()).all()
    assert df[CATEGORICAL_FEATURES].isna().sum().sum() == 0


def test_target_is_binary():
    df = generate_dataset(SMALL_CONFIG)
    assert set(df[TARGET_COLUMN].unique()) <= {0, 1}


def test_boolean_features_are_strictly_zero_or_one():
    df = generate_dataset(SMALL_CONFIG)
    assert set(df["retry_eligible"].unique()) <= {0.0, 1.0}
    assert set(df["fraud_signal"].unique()) <= {0.0, 1.0}


def test_categorical_values_are_within_expected_domains():
    df = generate_dataset(SMALL_CONFIG)
    assert set(df["decline_code"].unique()) <= {c.value for c in DeclineCode}
    assert set(df["decline_class"].unique()) <= {c.value for c in DeclineClass}
    assert set(df["currency"].unique()) <= {"usd", "eur", "gbp"}


def test_retry_eligible_and_fraud_signal_are_consistent_with_the_decline_taxonomy():
    from app.domain.decline_taxonomy import diagnose

    df = generate_dataset(SMALL_CONFIG)
    for _, row in df.sample(min(200, len(df)), random_state=0).iterrows():
        diag = diagnose(DeclineCode(row["decline_code"]))
        assert bool(row["retry_eligible"]) == (ActionType.RETRY_PAYMENT in diag.relevant_actions)
        assert bool(row["fraud_signal"]) == (diag.decline_class == DeclineClass.FRAUD)


def test_class_distribution_is_plausible_not_degenerate():
    """A larger, more representative run — the actual population balance
    used for training, not just the small fixture above."""
    df = generate_dataset(GeneratorConfig(n_customers=400, seed=42))
    positive_rate = df[TARGET_COLUMN].mean()
    assert 0.05 < positive_rate < 0.60, f"positive rate {positive_rate} looks degenerate, not plausible"


def test_no_single_feature_perfectly_determines_the_target():
    """A leakage guard: even the strongest legitimate signals (retry
    eligibility, fraud) should not correlate with the outcome so strongly
    that the label is effectively already present in a feature — the
    hidden generator's noise term (see training/synthetic_data.py) exists
    specifically to prevent this."""
    df = generate_dataset(GeneratorConfig(n_customers=400, seed=42))
    y = df[TARGET_COLUMN]
    for col in NUMERIC_FEATURES:
        corr = df[col].corr(y)
        if pd.isna(corr):
            continue
        assert abs(corr) < 0.90, f"{col} correlates {corr:.3f} with the target — investigate for leakage"


def test_historical_features_are_causally_prior_never_from_the_future():
    """The first event recorded for any customer must show zero prior
    history — there is nothing before it to have leaked from."""
    df = generate_dataset(GeneratorConfig(n_customers=100, seed=3))
    zero_history_rows = df[
        (df["customer_prior_successful_attempts"] == 0) & (df["customer_prior_failed_attempts"] == 0)
    ]
    assert len(zero_history_rows) > 0
    # A customer's very first attempt has no established recovery rate signal
    # yet — it must fall back to the neutral prior, not a leaked value.
    assert (zero_history_rows["customer_prior_recovery_rate"] == 0.5).all()


def test_training_module_does_not_import_the_hidden_ground_truth_function():
    """Structural separation check: training/train.py must only ever see
    realized (features, outcome) rows, never the scoring function that
    generated them."""
    import inspect

    from training import train as train_module

    source = inspect.getsource(train_module)
    assert "_hidden_recovery_logit" not in source
