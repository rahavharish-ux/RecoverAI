from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeatureContributionOut(BaseModel):
    feature: str
    value: float | str
    direction: str
    weight: float
    is_exact_contribution: bool


class ModelVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_name: str
    algorithm: str
    version: str
    dataset_version: str
    feature_schema_version: str
    is_calibrated: bool
    operating_threshold: float
    trained_at: datetime
    is_active: bool


class PredictionOut(BaseModel):
    id: int
    case_id: int
    payment_attempt_id: int
    recovery_probability: float
    confidence_band: str
    predicted_at: datetime
    model_version: ModelVersionOut
    top_contributions: list[FeatureContributionOut]
    expected_values_cents: dict[str, int] = {}
    note: str = (
        "recovery_probability is a sandbox model's estimate, trained and evaluated on "
        "synthetic data. It is advisory only — it never bypasses policy eligibility, "
        "and is not a claim about real-world recovery rates."
    )


class EvaluationSummaryOut(BaseModel):
    model_version: ModelVersionOut
    report: dict
