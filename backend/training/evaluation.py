"""Reusable evaluation-metric computation. Used by training/train.py to
produce the numbers written into a model_versions row, and exercised
directly by tests — the metrics reported are computed the same way they're
tested, not assembled by hand at report-writing time."""

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if len(set(y_true.tolist())) > 1 else None,
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
        "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0,
        "positive_rate_actual": float(np.mean(y_true)),
        "positive_rate_predicted": float(np.mean(y_pred)),
        "n": int(len(y_true)),
    }


def sweep_thresholds(y_true: np.ndarray, y_prob: np.ndarray, thresholds: list[float]) -> list[dict]:
    return [compute_metrics(y_true, y_prob, t) for t in thresholds]


def best_threshold_by_f1(y_true: np.ndarray, y_prob: np.ndarray, thresholds: list[float]) -> dict:
    sweep = sweep_thresholds(y_true, y_prob, thresholds)
    return max(sweep, key=lambda m: m["f1"])


def calibration_curve_data(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> dict:
    fraction_of_positives, mean_predicted_value = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="quantile"
    )
    return {
        "mean_predicted_value": [float(v) for v in mean_predicted_value],
        "fraction_of_positives": [float(v) for v in fraction_of_positives],
        "n_bins_requested": n_bins,
        "n_bins_actual": len(mean_predicted_value),
    }
