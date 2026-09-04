import { getDashboardSummary } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatPercent } from '../../lib/format'
import { META_LABEL_CLASS } from '../../lib/theme'
import { Card } from '../ui/Card'
import { ErrorState, LoadingState } from '../ui/States'

interface Kpi {
  label: string
  value: string
  tone: 'neutral' | 'success' | 'warning' | 'danger' | 'brand'
  caption?: string
}

const TONE_STYLES: Record<Kpi['tone'], string> = {
  neutral: 'text-ink',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
  brand: 'text-brand',
}

export function KpiCards() {
  const { data, loading, error } = useFetch(getDashboardSummary, [])

  if (loading) return <LoadingState label="Loading KPIs…" />
  if (error) return <ErrorState message={error} />
  if (!data) return null

  // recovery_rate = resolved / (resolved + escalated) among cases that
  // have already reached a terminal outcome — a "success rate of closed
  // cases" metric. It is NOT recovered / all cases ever opened (that's
  // the funnel's "Measure — Recovered" stage, a different denominator
  // that also counts cases still in progress) — the caption exists so
  // the two numbers are never mistaken for the same thing.
  const recoveryRateCaption =
    data.recovery_rate === null
      ? 'No cases closed yet'
      : data.active_recovery_cases > 0
        ? `Of closed cases — ${data.active_recovery_cases} still active`
        : 'Of closed cases'

  // Revenue at Risk lives in the hero above — it isn't repeated here.
  const kpis: Kpi[] = [
    { label: 'Recovery Rate', value: formatPercent(data.recovery_rate), tone: 'neutral', caption: recoveryRateCaption },
    { label: 'Active Recovery Cases', value: String(data.active_recovery_cases), tone: 'brand' },
    { label: 'Failed Payments', value: String(data.failed_payments), tone: 'neutral' },
    { label: 'Human Escalations', value: String(data.human_escalations), tone: data.human_escalations > 0 ? 'danger' : 'neutral' },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {kpis.map((kpi) => (
        <Card key={kpi.label}>
          <p className={META_LABEL_CLASS}>{kpi.label}</p>
          <p className={`mt-1.5 text-2xl font-bold tabular-nums ${TONE_STYLES[kpi.tone]}`}>{kpi.value}</p>
          {kpi.caption && <p className="mt-0.5 text-xs text-faint">{kpi.caption}</p>}
        </Card>
      ))}
    </div>
  )
}
