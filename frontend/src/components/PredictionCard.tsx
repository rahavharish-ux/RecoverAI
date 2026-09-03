import type { ConfidenceBand, Prediction } from '../types/prediction'

const BAND_STYLES: Record<ConfidenceBand, string> = {
  high: 'bg-success/15 text-success border-success/30',
  medium: 'bg-warning/15 text-warning border-warning/30',
  low: 'bg-surface-2 text-muted border-line-strong',
}

const DIRECTION_STYLES: Record<string, string> = {
  increases: 'text-success',
  decreases: 'text-danger',
  'n/a': 'text-faint',
}

const DIRECTION_ARROWS: Record<string, string> = {
  increases: '↑',
  decreases: '↓',
  'n/a': '—',
}

function formatFeatureValue(value: number | string): string {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
  }
  return value
}

function formatFeatureName(feature: string): string {
  return feature.replaceAll('_', ' ')
}

/** A reusable PREDICT-stage result card: probability, confidence band,
 * and the features that drove it. Embedded in both Case Intelligence and
 * Model Intelligence's explainability example — one implementation, one
 * visual language, everywhere a prediction is shown. */
export function PredictionCard({ prediction }: { prediction: Prediction }) {
  const probabilityPct = Math.round(prediction.recovery_probability * 100)

  return (
    <div className="max-w-md space-y-4 rounded-lg border border-line bg-surface p-5 text-ink">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-faint">Recovery Probability</p>
          <p className="text-3xl font-bold tabular-nums">{probabilityPct}%</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-medium uppercase ${BAND_STYLES[prediction.confidence_band]}`}>
          {prediction.confidence_band} confidence
        </span>
      </div>

      {prediction.top_contributions.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-faint">Top Contributing Factors</p>
          <ul className="space-y-1.5">
            {prediction.top_contributions.map((c) => (
              <li key={c.feature} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-muted">
                  {formatFeatureName(c.feature)} = {formatFeatureValue(c.value)}
                </span>
                <span className={`shrink-0 ${DIRECTION_STYLES[c.direction]}`}>
                  {DIRECTION_ARROWS[c.direction]}
                  {!c.is_exact_contribution && <span className="ml-1 text-xs text-faint">(est.)</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-line pt-3 text-xs text-faint">
        <span>
          {prediction.model_version.algorithm} · {prediction.model_version.version}
        </span>
        <span>trained on {prediction.model_version.dataset_version}</span>
      </div>

      <p className="text-xs text-faint">{prediction.note}</p>
    </div>
  )
}
