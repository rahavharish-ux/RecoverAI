from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class ModelVersion(Base):
    """The model registry. Exactly one row may have is_active=True at a
    time — that's the model the live prediction service loads. Every field
    a stored prediction needs to be traced back to a specific, reproducible
    training run lives here rather than being re-derived at read time."""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(60))
    algorithm: Mapped[str] = mapped_column(String(60))
    version: Mapped[str] = mapped_column(String(30))
    dataset_version: Mapped[str] = mapped_column(String(80))
    feature_schema_version: Mapped[str] = mapped_column(String(30))
    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    operating_threshold: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSON)
    artifact_path: Mapped[str] = mapped_column(String(300))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class MLPrediction(Base):
    """One row per PREDICT-stage evaluation. Append-only, same spirit as
    case_events: a stored prediction is never edited, only superseded by a
    newer row when a case is re-scored."""

    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    payment_attempt_id: Mapped[int] = mapped_column(ForeignKey("payment_attempts.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    recovery_probability: Mapped[float] = mapped_column(Float)
    confidence_band: Mapped[str] = mapped_column(String(10))
    feature_snapshot: Mapped[dict] = mapped_column(JSON)
    top_contributions: Mapped[list] = mapped_column(JSON)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
