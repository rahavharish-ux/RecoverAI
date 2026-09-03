import type { ConfidenceBand, Prediction } from '../types/prediction'

const BAND_STYLES: Record<ConfidenceBand, string> = {
  high: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  low: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
}

const DIRECTION_STYLES: Record<string, string> = {
  increases: 'text-emerald-400',
  decreases: 'text-rose-400',
  'n/a': 'text-slate-500',
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

/** Minimum viable visualization for a PREDICT-stage result: probability,
 * confidence band, and the features that drove it. Deliberately not part
 * of a Case Detail page yet — the full dashboard is a later phase; this is
 * the reusable piece that page will embed. */
export function PredictionCard({ prediction }: { prediction: Prediction }) {
  const probabilityPct = Math.round(prediction.recovery_probability * 100)

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-5 text-slate-100 space-y-4 max-w-md">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400">Recovery probability</p>
          <p className="text-3xl font-semibold tabular-nums">{probabilityPct}%</p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-medium uppercase ${BAND_STYLES[prediction.confidence_band]}`}
        >
          {prediction.confidence_band} confidence
        </span>
      </div>

      {prediction.top_contributions.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Why</p>
          <ul className="space-y-1.5">
            {prediction.top_contributions.map((c) => (
              <li key={c.feature} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-slate-300">
                  {formatFeatureName(c.feature)} = {formatFeatureValue(c.value)}
                </span>
                <span className={`shrink-0 ${DIRECTION_STYLES[c.direction]}`}>
                  {DIRECTION_ARROWS[c.direction]}
                  {!c.is_exact_contribution && <span className="ml-1 text-slate-500 text-xs">(est.)</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-slate-800 pt-3 text-xs text-slate-500">
        <span>
          {prediction.model_version.algorithm} · {prediction.model_version.version}
        </span>
        <span>trained on {prediction.model_version.dataset_version}</span>
      </div>

      <p className="text-xs text-slate-500">{prediction.note}</p>
    </div>
  )
}
