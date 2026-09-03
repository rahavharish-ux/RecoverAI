from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ml import ModelVersion
from app.schemas.ml import EvaluationSummaryOut, ModelVersionOut

router = APIRouter(prefix="/ml", tags=["ml"])


def _get_active_model_or_404(db: Session) -> ModelVersion:
    row = (
        db.query(ModelVersion)
        .filter(ModelVersion.is_active.is_(True))
        .order_by(ModelVersion.trained_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No active model. Run `python -m training.train` from backend/ to train and register one.",
        )
    return row


@router.get("/model", response_model=ModelVersionOut)
def get_active_model_metadata(db: Session = Depends(get_db)) -> ModelVersionOut:
    """What model, trained on what data, is currently making predictions."""
    return ModelVersionOut.model_validate(_get_active_model_or_404(db))


@router.get("/evaluation", response_model=EvaluationSummaryOut)
def get_active_model_evaluation(db: Session = Depends(get_db)) -> EvaluationSummaryOut:
    """The full, honestly-measured evaluation report for the active model —
    baseline vs. candidate on the same held-out test set, calibration
    before/after, and the validation-driven threshold search. Exactly what
    training/train.py wrote; nothing recomputed or summarized here."""
    row = _get_active_model_or_404(db)
    return EvaluationSummaryOut(model_version=ModelVersionOut.model_validate(row), report=row.metrics)
