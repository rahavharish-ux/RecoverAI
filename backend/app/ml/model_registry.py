"""Loads the currently active trained model: the DB metadata row plus its
joblib artifact. No in-process caching — at this project's scale a fresh
load per request is fast (a small joblib bundle) and always correct, and it
avoids a stale-cache bug if a model is retrained under the same
dataset_version. A caching layer is a reasonable Phase 3+ optimization if
prediction volume ever makes this worth it."""

from dataclasses import dataclass
from typing import Any

import joblib
from sqlalchemy.orm import Session

from app.models.ml import ModelVersion


@dataclass(frozen=True)
class ActiveModel:
    model_version: ModelVersion
    calibrated_pipeline: Any
    algorithm: str
    operating_threshold: float
    explanation: dict


def get_active_model(db: Session) -> ActiveModel | None:
    row = (
        db.query(ModelVersion)
        .filter(ModelVersion.is_active.is_(True))
        .order_by(ModelVersion.trained_at.desc())
        .first()
    )
    if row is None:
        return None

    try:
        artifact = joblib.load(row.artifact_path)
    except FileNotFoundError:
        # Registry row exists but the file is gone (e.g. artifact dir
        # wasn't shipped). Degrade gracefully rather than raise — PREDICT
        # is best-effort, never load-bearing for the rest of the pipeline.
        return None

    return ActiveModel(
        model_version=row,
        calibrated_pipeline=artifact["calibrated_pipeline"],
        algorithm=artifact["algorithm"],
        operating_threshold=artifact["operating_threshold"],
        explanation=artifact["explanation"],
    )
