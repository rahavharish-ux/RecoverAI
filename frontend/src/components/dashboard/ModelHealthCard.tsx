import { getActiveEvaluation, getActiveModel } from '../../api/ml'
import { useFetch } from '../../hooks/useFetch'
import { getSplitInfo, getTestMetrics } from '../../types/ml'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

export function ModelHealthCard() {
  const model = useFetch(getActiveModel, [])
  const evaluation = useFetch(getActiveEvaluation, [])

  const loading = model.loading || evaluation.loading
  const error = model.error ?? evaluation.error

  return (
    <Card eyebrow="Predict" title="Recovery Prediction Model">
      {loading && <LoadingState label="Loading model…" />}
      {error && <ErrorState message={error} />}
      {!loading && !error && !model.data && (
        <EmptyState message="No model trained yet." action={{ label: 'Run python -m training.train from backend/' }} />
      )}
      {model.data && (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-y-2">
            <span className="text-faint">Algorithm</span>
            <span className="text-right text-ink">{model.data.algorithm}</span>
            <span className="text-faint">Version</span>
            <span className="text-right font-mono text-xs text-muted">{model.data.version}</span>
            <span className="text-faint">Feature schema</span>
            <span className="text-right font-mono text-xs text-muted">{model.data.feature_schema_version}</span>
            <span className="text-faint">Calibrated</span>
            <span className="text-right text-ink">{model.data.is_calibrated ? 'Yes (isotonic)' : 'No'}</span>
            <span className="text-faint">Operating threshold</span>
            <span className="text-right tabular-nums text-ink">{model.data.operating_threshold}</span>
          </div>

          {evaluation.data && (
            <>
              <div className="rounded-md border border-warning/25 bg-warning/5 px-3 py-1.5 text-xs text-warning">
                Synthetic Sandbox Evaluation — not a claim about real-world payment data.
              </div>
              {(() => {
                const metrics = getTestMetrics(evaluation.data.report)
                const split = getSplitInfo(evaluation.data.report)
                if (!metrics) return null
                return (
                  <div className="grid grid-cols-2 gap-y-2 border-t border-line pt-3">
                    <span className="text-faint">ROC-AUC</span>
                    <span className="text-right tabular-nums text-ink">{metrics.roc_auc?.toFixed(3) ?? '—'}</span>
                    <span className="text-faint">PR-AUC</span>
                    <span className="text-right tabular-nums text-ink">{metrics.pr_auc.toFixed(3)}</span>
                    <span className="text-faint">Brier score</span>
                    <span className="text-right tabular-nums text-ink">{metrics.brier_score.toFixed(3)}</span>
                    {split && (
                      <>
                        <span className="text-faint">Test set size</span>
                        <span className="text-right tabular-nums text-ink">{split.test_n} cases</span>
                      </>
                    )}
                  </div>
                )
              })()}
            </>
          )}
        </div>
      )}
    </Card>
  )
}
