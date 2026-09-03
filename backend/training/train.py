"""Training orchestration for the PREDICT stage's recovery-probability
model. Consumes training.synthetic_data's output as an opaque dataframe of
realized (features, outcome) rows — it never imports the hidden
ground-truth scoring function, exactly as a real training pipeline would
never see the process that generated its historical data.

Run from backend/:  python -m training.train
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.schema import CATEGORICAL_FEATURES, FEATURE_SCHEMA_VERSION, NUMERIC_FEATURES, TARGET_COLUMN
from training import evaluation
from training.synthetic_data import GeneratorConfig, generate_dataset

THRESHOLD_GRID = [round(t, 2) for t in np.arange(0.05, 0.96, 0.05)]
RANDOM_STATE = 42


@dataclass(frozen=True)
class TrainConfig:
    generator: GeneratorConfig = GeneratorConfig()
    test_size: float = 0.15
    val_size: float = 0.15  # of the full dataset, not of the remainder
    artifact_root: str = "./ml_artifacts"


def _build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )


def _build_pipeline(algorithm: str) -> Pipeline:
    if algorithm == "logistic_regression":
        model = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE)
    elif algorithm == "random_forest":
        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    return Pipeline([("preprocess", _build_preprocessor()), ("model", model)])


def _split(df: pd.DataFrame, config: TrainConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y = df[TARGET_COLUMN]
    train_val, test = train_test_split(
        df, test_size=config.test_size, stratify=y, random_state=RANDOM_STATE
    )
    val_fraction_of_remainder = config.val_size / (1 - config.test_size)
    train, val = train_test_split(
        train_val,
        test_size=val_fraction_of_remainder,
        stratify=train_val[TARGET_COLUMN],
        random_state=RANDOM_STATE,
    )
    _assert_no_cross_split_duplicates(train, val, test)
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def _assert_no_cross_split_duplicates(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame) -> None:
    def row_hashes(frame: pd.DataFrame) -> set:
        return set(pd.util.hash_pandas_object(frame, index=False).tolist())

    train_h, val_h, test_h = row_hashes(train), row_hashes(val), row_hashes(test)
    overlap = (train_h & val_h) | (train_h & test_h) | (val_h & test_h)
    if overlap:
        raise RuntimeError(
            f"{len(overlap)} row(s) hash-identical across splits — refusing to train on "
            "contaminated data. This should be statistically near-impossible with this "
            "generator; investigate before proceeding."
        )


def _extract_explanation_artifacts(pipeline: Pipeline, X_train: pd.DataFrame) -> dict:
    preprocessor: ColumnTransformer = pipeline.named_steps["preprocess"]
    model = pipeline.named_steps["model"]
    feature_names = list(preprocessor.get_feature_names_out())
    scaler: StandardScaler = preprocessor.named_transformers_["num"]

    if hasattr(model, "coef_"):
        weights = model.coef_[0]
        kind = "coefficient"
    else:
        weights = model.feature_importances_
        kind = "importance"

    return {
        "kind": kind,
        "feature_names": feature_names,
        "weights": [float(w) for w in weights],
        "numeric_feature_medians": {col: float(X_train[col].median()) for col in NUMERIC_FEATURES},
        "numeric_feature_means": {col: float(m) for col, m in zip(NUMERIC_FEATURES, scaler.mean_)},
        "numeric_feature_scales": {col: float(s) for col, s in zip(NUMERIC_FEATURES, scaler.scale_)},
    }


def run(config: TrainConfig | None = None, session_factory=None) -> dict:
    """`session_factory`, if given, overrides where the trained model gets
    registered — used by tests to point registration at an isolated
    in-memory database instead of the real dev DB (see
    tests/integration/test_ml_training_pipeline.py)."""
    config = config or TrainConfig()
    generated_at = datetime.now(timezone.utc)

    df = generate_dataset(config.generator)
    train, val, test = _split(df, config)

    X_train, y_train = train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train[TARGET_COLUMN].to_numpy()
    X_val, y_val = val[NUMERIC_FEATURES + CATEGORICAL_FEATURES], val[TARGET_COLUMN].to_numpy()
    X_test, y_test = test[NUMERIC_FEATURES + CATEGORICAL_FEATURES], test[TARGET_COLUMN].to_numpy()

    # --- Fit baseline and candidate, raw (uncalibrated), on TRAIN only ---
    baseline_pipeline = _build_pipeline("logistic_regression")
    baseline_pipeline.fit(X_train, y_train)
    candidate_pipeline = _build_pipeline("random_forest")
    candidate_pipeline.fit(X_train, y_train)

    baseline_val_prob = baseline_pipeline.predict_proba(X_val)[:, 1]
    candidate_val_prob = candidate_pipeline.predict_proba(X_val)[:, 1]
    baseline_val_metrics = evaluation.compute_metrics(y_val, baseline_val_prob, threshold=0.5)
    candidate_val_metrics = evaluation.compute_metrics(y_val, candidate_val_prob, threshold=0.5)

    # Model selection happens on VALIDATION only, decided before the test
    # set is ever touched for anything but final reporting.
    selected_algorithm = (
        "random_forest" if candidate_val_metrics["pr_auc"] >= baseline_val_metrics["pr_auc"] else "logistic_regression"
    )
    selected_pipeline = candidate_pipeline if selected_algorithm == "random_forest" else baseline_pipeline

    # --- Final, honest baseline vs candidate comparison on the untouched TEST set ---
    baseline_test_prob = baseline_pipeline.predict_proba(X_test)[:, 1]
    candidate_test_prob = candidate_pipeline.predict_proba(X_test)[:, 1]
    baseline_test_metrics = evaluation.compute_metrics(y_test, baseline_test_prob, threshold=0.5)
    candidate_test_metrics = evaluation.compute_metrics(y_test, candidate_test_prob, threshold=0.5)

    # --- Calibrate the selected model (5-fold cross-fit on TRAIN only) ---
    calibrated_pipeline = CalibratedClassifierCV(
        _build_pipeline(selected_algorithm), method="isotonic", cv=5
    )
    calibrated_pipeline.fit(X_train, y_train)

    selected_raw_test_prob = candidate_test_prob if selected_algorithm == "random_forest" else baseline_test_prob
    calibrated_test_prob = calibrated_pipeline.predict_proba(X_test)[:, 1]

    raw_test_metrics_at_05 = evaluation.compute_metrics(y_test, selected_raw_test_prob, threshold=0.5)
    calibrated_test_metrics_at_05 = evaluation.compute_metrics(y_test, calibrated_test_prob, threshold=0.5)
    raw_calibration_curve = evaluation.calibration_curve_data(y_test, selected_raw_test_prob)
    calibrated_calibration_curve = evaluation.calibration_curve_data(y_test, calibrated_test_prob)

    # --- Threshold selection: validation only, on the calibrated model ---
    calibrated_val_prob = calibrated_pipeline.predict_proba(X_val)[:, 1]
    threshold_sweep = evaluation.sweep_thresholds(y_val, calibrated_val_prob, THRESHOLD_GRID)
    best_threshold_result = evaluation.best_threshold_by_f1(y_val, calibrated_val_prob, THRESHOLD_GRID)
    operating_threshold = best_threshold_result["threshold"]

    calibrated_test_metrics_at_operating_threshold = evaluation.compute_metrics(
        y_test, calibrated_test_prob, threshold=operating_threshold
    )

    explanation_source_pipeline = candidate_pipeline if selected_algorithm == "random_forest" else baseline_pipeline
    explanation_artifacts = _extract_explanation_artifacts(explanation_source_pipeline, X_train)

    report = {
        "generated_at": generated_at.isoformat(),
        "dataset_version": config.generator.dataset_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "split": {
            "train_n": len(train),
            "val_n": len(val),
            "test_n": len(test),
            "train_positive_rate": float(y_train.mean()),
            "val_positive_rate": float(y_val.mean()),
            "test_positive_rate": float(y_test.mean()),
        },
        "model_comparison_on_test_set": {
            "baseline_logistic_regression": baseline_test_metrics,
            "candidate_random_forest": candidate_test_metrics,
        },
        "selection": {
            "selected_algorithm": selected_algorithm,
            "selection_metric": "pr_auc on validation set",
            "baseline_val_pr_auc": baseline_val_metrics["pr_auc"],
            "candidate_val_pr_auc": candidate_val_metrics["pr_auc"],
        },
        "calibration": {
            "method": "isotonic (sklearn CalibratedClassifierCV, cv=5, fit on train only)",
            "raw_test_metrics_at_0.5": raw_test_metrics_at_05,
            "calibrated_test_metrics_at_0.5": calibrated_test_metrics_at_05,
            "raw_calibration_curve": raw_calibration_curve,
            "calibrated_calibration_curve": calibrated_calibration_curve,
            "brier_improved": calibrated_test_metrics_at_05["brier_score"] < raw_test_metrics_at_05["brier_score"],
        },
        "threshold_selection": {
            "method": "argmax F1 over a 0.05-step grid, evaluated on the VALIDATION set using "
            "calibrated probabilities. Not test-set-driven, and not asserted to be the "
            "objectively 'correct' threshold — a configured operating point.",
            "grid": THRESHOLD_GRID,
            "operating_threshold": operating_threshold,
            "validation_metrics_at_operating_threshold": best_threshold_result,
            "test_metrics_at_operating_threshold": calibrated_test_metrics_at_operating_threshold,
        },
    }

    artifact_dir = Path(config.artifact_root) / config.generator.dataset_version
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "model.joblib"
    joblib.dump(
        {
            "calibrated_pipeline": calibrated_pipeline,
            "algorithm": selected_algorithm,
            "operating_threshold": operating_threshold,
            "explanation": explanation_artifacts,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
        },
        artifact_path,
    )
    report_path = artifact_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    model_version_id = _register_model_version(
        algorithm=selected_algorithm,
        dataset_version=config.generator.dataset_version,
        metrics=report,
        artifact_path=str(artifact_path),
        operating_threshold=operating_threshold,
        session_factory=session_factory,
    )
    report["model_version_id"] = model_version_id
    report["artifact_path"] = str(artifact_path)
    return report


def _register_model_version(
    *,
    algorithm: str,
    dataset_version: str,
    metrics: dict,
    artifact_path: str,
    operating_threshold: float,
    session_factory=None,
) -> int:
    from app.models.ml import ModelVersion

    if session_factory is None:
        from app.db.session import SessionLocal, engine
        from app.models import Base

        Base.metadata.create_all(bind=engine)
        session_factory = SessionLocal

    db = session_factory()
    try:
        db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).update({"is_active": False})
        row = ModelVersion(
            model_name="recovery_probability",
            algorithm=algorithm,
            version=f"v{int(datetime.now(timezone.utc).timestamp())}",
            dataset_version=dataset_version,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            is_calibrated=True,
            operating_threshold=operating_threshold,
            metrics=metrics,
            artifact_path=artifact_path,
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _print_summary(report: dict) -> None:
    split = report["split"]
    sel = report["selection"]
    cal = report["calibration"]
    thr = report["threshold_selection"]
    print(f"dataset_version:        {report['dataset_version']}")
    print(f"train/val/test sizes:   {split['train_n']} / {split['val_n']} / {split['test_n']}")
    print(
        f"positive rate (t/v/t):  {split['train_positive_rate']:.3f} / "
        f"{split['val_positive_rate']:.3f} / {split['test_positive_rate']:.3f}"
    )
    print(f"selected algorithm:     {sel['selected_algorithm']} (by validation PR-AUC)")
    print(f"  baseline val PR-AUC:  {sel['baseline_val_pr_auc']:.4f}")
    print(f"  candidate val PR-AUC: {sel['candidate_val_pr_auc']:.4f}")
    print(f"raw test Brier:         {cal['raw_test_metrics_at_0.5']['brier_score']:.4f}")
    print(f"calibrated test Brier:  {cal['calibrated_test_metrics_at_0.5']['brier_score']:.4f}")
    print(f"operating threshold:    {thr['operating_threshold']}")
    print(f"model_version_id:       {report['model_version_id']}")
    print(f"artifact:               {report['artifact_path']}")


if __name__ == "__main__":
    result = run()
    _print_summary(result)
