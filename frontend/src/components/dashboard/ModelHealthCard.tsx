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
        <EmptyState message="No model trained yet. Run `python -m training.train` from backend/." />
      )}
      {model.data && (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-y-2">
            <span className="text-slate-500">Algorithm</span>
            <span className="text-right text-slate-200">{model.data.algorithm}</span>
            <span className="text-slate-500">Version</span>
            <span className="text-right font-mono text-xs text-slate-300">{model.data.version}</span>
            <span className="text-slate-500">Feature schema</span>
            <span className="text-right font-mono text-xs text-slate-300">{model.data.feature_schema_version}</span>
            <span className="text-slate-500">Calibrated</span>
            <span className="text-right text-slate-200">{model.data.is_calibrated ? 'Yes (isotonic)' : 'No'}</span>
            <span className="text-slate-500">Operating threshold</span>
            <span className="text-right tabular-nums text-slate-200">{model.data.operating_threshold}</span>
          </div>

          {evaluation.data && (
            <>
              <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-1.5 text-xs text-amber-300">
                Synthetic Sandbox Evaluation — not a claim about real-world payment data.
              </div>
              {(() => {
                const metrics = getTestMetrics(evaluation.data.report)
                const split = getSplitInfo(evaluation.data.report)
                if (!metrics) return null
                return (
                  <div className="grid grid-cols-2 gap-y-2 border-t border-slate-800 pt-3">
                    <span className="text-slate-500">ROC-AUC</span>
                    <span className="text-right tabular-nums text-slate-200">{metrics.roc_auc?.toFixed(3) ?? '—'}</span>
                    <span className="text-slate-500">PR-AUC</span>
                    <span className="text-right tabular-nums text-slate-200">{metrics.pr_auc.toFixed(3)}</span>
                    <span className="text-slate-500">Brier score</span>
                    <span className="text-right tabular-nums text-slate-200">{metrics.brier_score.toFixed(3)}</span>
                    {split && (
                      <>
                        <span className="text-slate-500">Test set size</span>
                        <span className="text-right tabular-nums text-slate-200">{split.test_n} cases</span>
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
