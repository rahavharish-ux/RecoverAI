export interface ModelVersion {
  id: number
  model_name: string
  algorithm: string
  version: string
  dataset_version: string
  feature_schema_version: string
  is_calibrated: boolean
  operating_threshold: number
  trained_at: string
  is_active: boolean
}

/** The evaluation report's shape is whatever training/train.py wrote (see
 * backend/training/train.py) — treated as an opaque bag of metrics here
 * rather than re-declared field by field, since one of its real keys
 * ("calibrated_test_metrics_at_0.5") isn't even a valid TS identifier. */
export type EvaluationReport = Record<string, unknown>

export interface EvaluationSummary {
  model_version: ModelVersion
  report: EvaluationReport
}

export interface TestSetMetrics {
  roc_auc: number | null
  pr_auc: number
  brier_score: number
  precision: number
  recall: number
  f1: number
}

export function getTestMetrics(report: EvaluationReport): TestSetMetrics | null {
  const calibration = report.calibration as Record<string, unknown> | undefined
  const metrics = calibration?.['calibrated_test_metrics_at_0.5'] as Partial<TestSetMetrics> | undefined
  if (!metrics) return null
  return {
    roc_auc: metrics.roc_auc ?? null,
    pr_auc: metrics.pr_auc ?? 0,
    brier_score: metrics.brier_score ?? 0,
    precision: metrics.precision ?? 0,
    recall: metrics.recall ?? 0,
    f1: metrics.f1 ?? 0,
  }
}

export function getSplitInfo(report: EvaluationReport): { train_n: number; val_n: number; test_n: number } | null {
  const split = report.split as { train_n: number; val_n: number; test_n: number } | undefined
  return split ?? null
}

export function getBrierImproved(report: EvaluationReport): boolean | null {
  const calibration = report.calibration as Record<string, unknown> | undefined
  return typeof calibration?.brier_improved === 'boolean' ? calibration.brier_improved : null
}
