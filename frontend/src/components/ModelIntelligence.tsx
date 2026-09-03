import { getRecentDecisions } from '../api/dashboard'
import { getCasePrediction } from '../api/predictions'
import { useFetch } from '../hooks/useFetch'
import { getBrierImproved, getSplitInfo, getTestMetrics } from '../types/ml'
import { getActiveEvaluation, getActiveModel } from '../api/ml'
import { Card } from './ui/Card'
import { EmptyState, ErrorState, LoadingState } from './ui/States'
import { PredictionCard } from './PredictionCard'

export function ModelIntelligence() {
  const model = useFetch(getActiveModel, [])
  const evaluation = useFetch(getActiveEvaluation, [])
  const recentDecisions = useFetch(() => getRecentDecisions(1), [])
  const sampleCaseId = recentDecisions.data?.[0]?.case_id ?? null
  const samplePrediction = useFetch(async () => (sampleCaseId ? getCasePrediction(sampleCaseId) : null), [sampleCaseId])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Model Intelligence</h1>
        <p className="text-sm text-slate-500">
          The active recovery-probability model — what it is, how it was evaluated, and an example of how it
          explains a single prediction.
        </p>
      </header>

      <Card eyebrow="Predict" title="Active Model">
        {model.loading && <LoadingState label="Loading model…" />}
        {model.error && <ErrorState message={model.error} />}
        {!model.loading && !model.data && (
          <EmptyState message="No model trained yet. Run `python -m training.train` from backend/." />
        )}
        {model.data && (
          <div className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-slate-500">Algorithm</p>
              <p className="text-slate-200">{model.data.algorithm}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Version</p>
              <p className="font-mono text-xs text-slate-300">{model.data.version}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Dataset</p>
              <p className="font-mono text-xs text-slate-300">{model.data.dataset_version}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Feature schema</p>
              <p className="font-mono text-xs text-slate-300">{model.data.feature_schema_version}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Calibrated</p>
              <p className="text-slate-200">{model.data.is_calibrated ? 'Yes (isotonic)' : 'No'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Operating threshold</p>
              <p className="tabular-nums text-slate-200">{model.data.operating_threshold}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Trained</p>
              <p className="text-slate-200">{new Date(model.data.trained_at).toLocaleString()}</p>
            </div>
          </div>
        )}
      </Card>

      {evaluation.data &&
        (() => {
          const metrics = getTestMetrics(evaluation.data.report)
          const split = getSplitInfo(evaluation.data.report)
          const brierImproved = getBrierImproved(evaluation.data.report)
          return (
            <Card eyebrow="Honestly Measured" title="Synthetic Sandbox Evaluation">
              <div className="mb-4 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
                Computed on synthetic, generated sandbox data — not real payment history. Not a claim about
                real-world recovery rates.
              </div>
              {metrics && (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Metric label="ROC-AUC" value={metrics.roc_auc?.toFixed(3) ?? '—'} />
                  <Metric label="PR-AUC" value={metrics.pr_auc.toFixed(3)} />
                  <Metric label="Brier Score" value={metrics.brier_score.toFixed(3)} />
                  <Metric label="F1" value={metrics.f1.toFixed(3)} />
                </div>
              )}
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 border-t border-slate-800 pt-3 text-xs text-slate-500">
                {split && (
                  <span>
                    Train/val/test split: {split.train_n} / {split.val_n} / {split.test_n}
                  </span>
                )}
                {brierImproved !== null && (
                  <span>Calibration {brierImproved ? 'improved' : 'did not improve'} the Brier score</span>
                )}
              </div>
            </Card>
          )
        })()}

      <Card eyebrow="Explainability" title="Example Prediction Explanation">
        {recentDecisions.loading || samplePrediction.loading ? (
          <LoadingState label="Loading example…" />
        ) : sampleCaseId === null ? (
          <EmptyState message="No predictions yet — try the Demo Center to generate one." />
        ) : samplePrediction.data ? (
          <div className="space-y-2">
            <p className="text-xs text-slate-500">From the most recent scored case, Case #{sampleCaseId}:</p>
            <PredictionCard prediction={samplePrediction.data} />
          </div>
        ) : (
          <EmptyState message="No prediction stored for the most recent case." />
        )}
      </Card>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-slate-100">{value}</p>
    </div>
  )
}
