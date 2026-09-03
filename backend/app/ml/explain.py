"""Turns a trained model's global weights (logistic-regression coefficients,
or a tree ensemble's native impurity-based `feature_importances_`) plus one
specific feature row into a ranked, human-readable list of contributing
features.

Logistic regression gets a TRUE per-instance contribution: coefficient x
standardized value is exactly the term's share of the predicted logit —
`is_exact_contribution=True`. A tree ensemble has no such linear
decomposition without an extra dependency (SHAP), so it instead gets the
model's global importance for that feature paired with how this instance's
own value compares to the training population's median, as an honestly
labeled direction proxy — `is_exact_contribution=False`. No SHAP or other
added dependency is used.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureContribution:
    feature: str
    value: float | str
    direction: str  # "increases" | "decreases" | "n/a"
    weight: float
    is_exact_contribution: bool

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "value": self.value,
            "direction": self.direction,
            "weight": round(self.weight, 6),
            "is_exact_contribution": self.is_exact_contribution,
        }


def explain_prediction(
    *,
    explanation_artifacts: dict,
    feature_row: dict,
    categorical_features: list[str],
    top_k: int = 5,
) -> list[FeatureContribution]:
    kind = explanation_artifacts["kind"]
    names = explanation_artifacts["feature_names"]
    weights = explanation_artifacts["weights"]
    medians = explanation_artifacts["numeric_feature_medians"]
    means = explanation_artifacts.get("numeric_feature_means", {})
    scales = explanation_artifacts.get("numeric_feature_scales", {})

    contributions: list[FeatureContribution] = []

    for raw_name, weight in zip(names, weights):
        prefix, _, rest = raw_name.partition("__")

        if prefix == "num":
            column = rest
            if column not in feature_row:
                continue
            value = feature_row[column]

            if kind == "coefficient":
                mean = means.get(column, 0.0)
                scale = scales.get(column, 1.0) or 1.0
                standardized = (value - mean) / scale
                signed_contribution = weight * standardized
                contributions.append(
                    FeatureContribution(
                        feature=column,
                        value=value,
                        direction="increases" if signed_contribution > 0 else "decreases",
                        weight=abs(signed_contribution),
                        is_exact_contribution=True,
                    )
                )
            else:
                median = medians.get(column, 0.0)
                direction = "increases" if value > median else "decreases" if value < median else "n/a"
                contributions.append(
                    FeatureContribution(
                        feature=column, value=value, direction=direction, weight=abs(weight), is_exact_contribution=False
                    )
                )

        else:  # "cat"
            body = rest
            matched_column = next((c for c in categorical_features if body.startswith(c + "_")), None)
            if matched_column is None:
                continue
            category_value = body[len(matched_column) + 1 :]
            if feature_row.get(matched_column) != category_value:
                continue  # this one-hot indicator isn't "on" for this instance
            contributions.append(
                FeatureContribution(
                    feature=matched_column,
                    value=category_value,
                    direction="increases" if weight > 0 else "decreases",
                    weight=abs(weight),
                    is_exact_contribution=(kind == "coefficient"),
                )
            )

    contributions.sort(key=lambda c: c.weight, reverse=True)
    return contributions[:top_k]
