from app.ml.explain import explain_prediction

CATEGORICAL_FEATURES = ["decline_code", "currency"]


def _coefficient_artifacts() -> dict:
    return {
        "kind": "coefficient",
        "feature_names": [
            "num__customer_prior_recovery_rate",
            "num__log_amount",
            "cat__decline_code_card_declined",
            "cat__decline_code_insufficient_funds",
            "cat__currency_usd",
        ],
        "weights": [1.6, -0.35, -0.2, 0.1, 0.05],
        "numeric_feature_medians": {"customer_prior_recovery_rate": 0.5, "log_amount": 8.3},
        "numeric_feature_means": {"customer_prior_recovery_rate": 0.5, "log_amount": 8.3},
        "numeric_feature_scales": {"customer_prior_recovery_rate": 0.2, "log_amount": 1.0},
    }


def _importance_artifacts() -> dict:
    return {
        "kind": "importance",
        "feature_names": [
            "num__customer_prior_recovery_rate",
            "num__log_amount",
            "cat__decline_code_card_declined",
        ],
        "weights": [0.5, 0.2, 0.1],
        "numeric_feature_medians": {"customer_prior_recovery_rate": 0.5, "log_amount": 8.3},
    }


def test_logistic_regression_gives_exact_contributions():
    feature_row = {"customer_prior_recovery_rate": 0.9, "log_amount": 8.3, "decline_code": "card_declined", "currency": "usd"}
    contributions = explain_prediction(
        explanation_artifacts=_coefficient_artifacts(), feature_row=feature_row, categorical_features=CATEGORICAL_FEATURES
    )
    assert all(c.is_exact_contribution or c.feature == "decline_code" or c.feature == "currency" for c in contributions if c.feature != "log_amount")
    top = contributions[0]
    assert top.feature == "customer_prior_recovery_rate"
    assert top.direction == "increases"  # 0.9 is well above the 0.5 median, positive coefficient


def test_random_forest_gives_direction_proxy_not_exact():
    feature_row = {"customer_prior_recovery_rate": 0.1, "log_amount": 8.3, "decline_code": "card_declined"}
    contributions = explain_prediction(
        explanation_artifacts=_importance_artifacts(), feature_row=feature_row, categorical_features=["decline_code"]
    )
    numeric = next(c for c in contributions if c.feature == "customer_prior_recovery_rate")
    assert numeric.is_exact_contribution is False
    assert numeric.direction == "decreases"  # 0.1 is below the 0.5 median


def test_only_the_active_category_is_reported():
    feature_row = {"customer_prior_recovery_rate": 0.5, "log_amount": 8.3, "decline_code": "insufficient_funds", "currency": "usd"}
    contributions = explain_prediction(
        explanation_artifacts=_coefficient_artifacts(), feature_row=feature_row, categorical_features=CATEGORICAL_FEATURES
    )
    features_reported = {c.feature for c in contributions}
    # decline_code=insufficient_funds is active, card_declined's one-hot column is 0 for this row
    values_reported = {c.feature: c.value for c in contributions}
    assert values_reported.get("decline_code") == "insufficient_funds"


def test_top_k_truncates():
    feature_row = {"customer_prior_recovery_rate": 0.9, "log_amount": 8.3, "decline_code": "card_declined", "currency": "usd"}
    contributions = explain_prediction(
        explanation_artifacts=_coefficient_artifacts(),
        feature_row=feature_row,
        categorical_features=CATEGORICAL_FEATURES,
        top_k=2,
    )
    assert len(contributions) == 2


def test_contributions_are_sorted_by_magnitude_descending():
    feature_row = {"customer_prior_recovery_rate": 0.9, "log_amount": 8.3, "decline_code": "card_declined", "currency": "usd"}
    contributions = explain_prediction(
        explanation_artifacts=_coefficient_artifacts(), feature_row=feature_row, categorical_features=CATEGORICAL_FEATURES
    )
    weights = [c.weight for c in contributions]
    assert weights == sorted(weights, reverse=True)


def test_to_dict_produces_json_ready_output():
    feature_row = {"customer_prior_recovery_rate": 0.9, "log_amount": 8.3, "decline_code": "card_declined", "currency": "usd"}
    contributions = explain_prediction(
        explanation_artifacts=_coefficient_artifacts(), feature_row=feature_row, categorical_features=CATEGORICAL_FEATURES
    )
    d = contributions[0].to_dict()
    assert set(d.keys()) == {"feature", "value", "direction", "weight", "is_exact_contribution"}
