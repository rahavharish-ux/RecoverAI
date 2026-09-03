"""The synthetic ground-truth generator for RecoverAI's PREDICT stage.

This is a SANDBOX data-generating process — hand-built, not fit to any real
payment data. Its output must never be presented as representative of
real-world recovery rates; its purpose is narrower: to produce a dataset
with genuine, realistic *relationships* between features and outcome (not
independent random columns), with irreducible noise, so training/train.py
has something honest to evaluate a model against.

Deliberately separated from training/train.py: the hidden scoring function
below is the ground truth a model is trying to recover from noisy,
partial evidence. training/train.py never imports it — it only ever sees
the realized (features, outcome) rows this module produces, exactly as a
real training pipeline would only ever see realized outcomes, never the
process that generated them.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.domain.enums import DeclineCode
from app.ml.features import RawFeatureInputs, compute_features
from app.ml.schema import NO_PRIOR_ATTEMPT_HOURS_SENTINEL, TARGET_COLUMN

DECLINE_CODE_WEIGHTS: dict[DeclineCode, float] = {
    DeclineCode.INSUFFICIENT_FUNDS: 0.26,
    DeclineCode.CARD_DECLINED: 0.22,
    DeclineCode.PROCESSOR_ERROR: 0.13,
    DeclineCode.EXPIRED_CARD: 0.15,
    DeclineCode.INVALID_METHOD: 0.08,
    DeclineCode.DO_NOT_HONOR: 0.11,
    DeclineCode.FRAUD_SUSPECTED: 0.05,
}
PLAN_TIERS = ["standard", "growth", "enterprise"]
PLAN_WEIGHTS = [0.55, 0.30, 0.15]
PLAN_BASE_AMOUNT_CENTS = {"standard": 2900, "growth": 7900, "enterprise": 24900}
PLAN_LOGIT_OFFSET = {"standard": 0.0, "growth": 0.15, "enterprise": 0.30}
BRANDS = ["visa", "mastercard", "amex"]
GATEWAYS = ["sim_gateway_a", "sim_gateway_b"]
CURRENCIES = ["usd", "eur", "gbp"]
CURRENCY_WEIGHTS = [0.80, 0.13, 0.07]


@dataclass(frozen=True)
class GeneratorConfig:
    n_customers: int = 1200
    avg_events_per_customer: float = 4.0
    seed: int = 42
    start_days_ago: int = 400

    @property
    def dataset_version(self) -> str:
        return f"synthetic-v1-seed{self.seed}-cust{self.n_customers}"


def _hidden_recovery_logit(
    *,
    retry_eligible: bool,
    fraud_signal: bool,
    decline_code: str,
    log_amount: float,
    method_age_days: float,
    tenure_days: float,
    prior_recovery_rate: float,
    retry_number: float,
    hours_since_last: float,
    invoice_age_days: float,
    plan_tier: str,
    txn_freq: float,
    hour: int,
    dow: int,
) -> float:
    """The GROUND TRUTH — never seen directly by any model, only sampled
    from (with noise, see generate_dataset). Not imported by train.py."""
    if fraud_signal:
        return -6.0  # a retried fraud-flagged charge essentially never succeeds
    if not retry_eligible:
        return -4.0  # hard declines (non-fraud): blind retry essentially never works

    score = -0.30
    score += {"insufficient_funds": 0.10, "card_declined": -0.20, "processor_error": 0.60}.get(
        decline_code, 0.0
    )
    score += -0.35 * ((log_amount - 8.3) / 1.0)
    score += 0.25 * ((method_age_days - 300.0) / 200.0)
    score += 0.30 * ((tenure_days - 400.0) / 300.0)
    score += 1.60 * (prior_recovery_rate - 0.5)
    # A genuine interaction, not just an additive term: repeated retries hurt
    # customers with a poor track record far more than customers with a
    # strong one. A purely linear-in-logit model cannot represent a product
    # of two continuous features directly — this is what gives a non-linear
    # candidate model a real chance to outperform logistic regression.
    score += -0.55 * retry_number * (1.0 - prior_recovery_rate)
    score += 0.20 * max(-2.0, min(2.0, (hours_since_last - 48.0) / 48.0))
    score += -0.15 * ((invoice_age_days - 2.0) / 2.0)
    score += PLAN_LOGIT_OFFSET.get(plan_tier, 0.0)
    score += 0.10 * ((txn_freq - 1.0) / 1.0)
    score += 0.10 if 8 <= hour <= 20 else -0.10
    score += 0.05 if dow < 5 else -0.05
    return score


def generate_dataset(config: GeneratorConfig = GeneratorConfig()) -> pd.DataFrame:
    """Deterministic given `config.seed` — same seed, same dataset, always."""
    rng = np.random.default_rng(config.seed)
    decline_codes = list(DECLINE_CODE_WEIGHTS.keys())
    weights = np.array([DECLINE_CODE_WEIGHTS[c] for c in decline_codes])
    decline_probs = weights / weights.sum()

    now = datetime.now(timezone.utc)
    rows: list[dict] = []

    for _ in range(config.n_customers):
        tenure_days = float(rng.gamma(shape=2.0, scale=180.0)) + 1.0
        plan_tier = str(rng.choice(PLAN_TIERS, p=PLAN_WEIGHTS))
        base_amount = PLAN_BASE_AMOUNT_CENTS[plan_tier]
        brand = str(rng.choice(BRANDS))
        method_age_days = float(rng.exponential(300.0)) + 1.0
        gateway = str(rng.choice(GATEWAYS))
        currency = str(rng.choice(CURRENCIES, p=CURRENCY_WEIGHTS))

        n_events = max(1, int(rng.poisson(config.avg_events_per_customer)))
        start = now - timedelta(days=int(rng.integers(30, config.start_days_ago)))

        prior_success = 0
        prior_fail = 0
        prior_recovery_actions = 0
        historical_amounts: list[float] = []
        last_attempt_at: datetime | None = None

        for event_idx in range(n_events):
            decline_code = decline_codes[int(rng.choice(len(decline_codes), p=decline_probs))]
            amount_cents = max(100, int(rng.lognormal(mean=math.log(base_amount), sigma=0.35)))
            invoice_age_days = float(rng.integers(0, 6))
            retry_number = float(rng.integers(0, 3)) if rng.random() < 0.4 else 0.0
            attempted_at = start + timedelta(
                days=event_idx * float(rng.uniform(3, 20)), hours=float(rng.integers(0, 24))
            )
            hours_since_last = (
                max(0.5, (attempted_at - last_attempt_at).total_seconds() / 3600.0)
                if last_attempt_at is not None
                else NO_PRIOR_ATTEMPT_HOURS_SENTINEL
            )

            # Historical aggregates are computed from events strictly BEFORE
            # this one — the running counters below are only updated after
            # this row is recorded, so nothing here leaks this event's own
            # outcome into its own features.
            inputs = RawFeatureInputs(
                amount_cents=amount_cents,
                currency=currency,
                decline_code=decline_code,
                payment_method_brand=brand,
                payment_method_age_days=method_age_days,
                customer_tenure_days=tenure_days,
                customer_plan_tier=plan_tier,
                customer_prior_successful_attempts=prior_success,
                customer_prior_failed_attempts=prior_fail,
                customer_prior_recovery_actions=prior_recovery_actions,
                customer_avg_historical_amount_cents=(
                    sum(historical_amounts) / len(historical_amounts)
                    if historical_amounts
                    else float(amount_cents)
                ),
                retry_number=retry_number,
                hours_since_last_attempt=hours_since_last,
                invoice_age_days=invoice_age_days,
                gateway=gateway,
                attempted_at=attempted_at,
            )
            features = compute_features(inputs)

            logit = _hidden_recovery_logit(
                retry_eligible=bool(features["retry_eligible"]),
                fraud_signal=bool(features["fraud_signal"]),
                decline_code=features["decline_code"],
                log_amount=features["log_amount"],
                method_age_days=features["payment_method_age_days"],
                tenure_days=features["customer_tenure_days"],
                prior_recovery_rate=features["customer_prior_recovery_rate"],
                retry_number=features["retry_number"],
                hours_since_last=features["hours_since_last_attempt"],
                invoice_age_days=features["invoice_age_days"],
                plan_tier=plan_tier,
                txn_freq=features["customer_txn_frequency_per_month"],
                hour=attempted_at.hour,
                dow=attempted_at.weekday(),
            )
            noisy_logit = logit + float(rng.normal(0.0, 0.5))  # irreducible noise
            probability = 1.0 / (1.0 + math.exp(-noisy_logit))
            outcome = bool(rng.random() < probability)

            row = dict(features)
            row[TARGET_COLUMN] = int(outcome)
            rows.append(row)

            if outcome:
                prior_success += 1
                if rng.random() < 0.3:
                    prior_recovery_actions += 1
            else:
                prior_fail += 1
            historical_amounts.append(float(amount_cents))
            last_attempt_at = attempted_at

    return pd.DataFrame(rows)
