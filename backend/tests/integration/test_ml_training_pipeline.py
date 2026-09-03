"""Exercises the real training pipeline end to end, at a small scale for
test speed, registering into an isolated in-memory DB — never the real dev
database. training/train.py's honest, actually-measured numbers (not these
small-scale sanity checks) are what the final report quotes; these tests
verify the pipeline's *mechanics* are correct."""

from app.models.ml import ModelVersion
from training.synthetic_data import GeneratorConfig
from training.train import TrainConfig, run

SMALL_CONFIG = TrainConfig(generator=GeneratorConfig(n_customers=250, seed=11))


def test_training_pipeline_runs_end_to_end_and_returns_a_complete_report(tmp_path, session_factory):
    config = TrainConfig(generator=GeneratorConfig(n_customers=250, seed=11), artifact_root=str(tmp_path))
    report = run(config, session_factory=session_factory)

    for key in ("split", "model_comparison_on_test_set", "selection", "calibration", "threshold_selection"):
        assert key in report

    split = report["split"]
    assert split["train_n"] + split["val_n"] + split["test_n"] > 0
    assert 0.0 < split["train_positive_rate"] < 1.0


def test_probabilities_and_metrics_are_within_valid_ranges(tmp_path, session_factory):
    config = TrainConfig(generator=GeneratorConfig(n_customers=250, seed=12), artifact_root=str(tmp_path))
    report = run(config, session_factory=session_factory)

    for model_metrics in report["model_comparison_on_test_set"].values():
        assert 0.0 <= model_metrics["precision"] <= 1.0
        assert 0.0 <= model_metrics["recall"] <= 1.0
        assert 0.0 <= model_metrics["f1"] <= 1.0
        assert model_metrics["roc_auc"] is None or 0.0 <= model_metrics["roc_auc"] <= 1.0
        assert 0.0 <= model_metrics["pr_auc"] <= 1.0
        assert 0.0 <= model_metrics["brier_score"] <= 1.0

    calibrated = report["calibration"]["calibrated_test_metrics_at_0.5"]
    assert 0.0 <= calibrated["brier_score"] <= 1.0
    threshold = report["threshold_selection"]["operating_threshold"]
    assert 0.0 < threshold < 1.0


def test_model_selection_is_documented_as_validation_driven(tmp_path, session_factory):
    config = TrainConfig(generator=GeneratorConfig(n_customers=250, seed=13), artifact_root=str(tmp_path))
    report = run(config, session_factory=session_factory)
    assert "validation" in report["selection"]["selection_metric"]
    assert "VALIDATION" in report["threshold_selection"]["method"]
    assert report["selection"]["selected_algorithm"] in ("logistic_regression", "random_forest")


def test_registers_exactly_one_active_model_version(tmp_path, session_factory):
    config = TrainConfig(generator=GeneratorConfig(n_customers=200, seed=14), artifact_root=str(tmp_path))
    run(config, session_factory=session_factory)

    db = session_factory()
    try:
        active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).all()
        assert len(active) == 1
    finally:
        db.close()


def test_retraining_deactivates_the_previous_model_version(tmp_path, session_factory):
    config = TrainConfig(generator=GeneratorConfig(n_customers=200, seed=15), artifact_root=str(tmp_path))
    first_report = run(config, session_factory=session_factory)

    config2 = TrainConfig(generator=GeneratorConfig(n_customers=200, seed=16), artifact_root=str(tmp_path))
    second_report = run(config2, session_factory=session_factory)

    db = session_factory()
    try:
        active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).all()
        assert len(active) == 1
        assert active[0].id == second_report["model_version_id"]
        assert active[0].id != first_report["model_version_id"]
    finally:
        db.close()


def test_artifact_files_are_written(tmp_path, session_factory):
    config = TrainConfig(generator=GeneratorConfig(n_customers=200, seed=17), artifact_root=str(tmp_path))
    report = run(config, session_factory=session_factory)

    from pathlib import Path

    artifact_path = Path(report["artifact_path"])
    assert artifact_path.exists()
    report_path = artifact_path.parent / "evaluation_report.json"
    assert report_path.exists()
