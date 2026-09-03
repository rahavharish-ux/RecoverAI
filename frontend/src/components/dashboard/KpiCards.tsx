import { getDashboardSummary } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, formatPercent } from '../../lib/format'
import { Card } from '../ui/Card'
import { ErrorState, LoadingState } from '../ui/States'

interface Kpi {
  label: string
  value: string
  tone: 'neutral' | 'positive' | 'warning' | 'danger'
}

const TONE_STYLES: Record<Kpi['tone'], string> = {
  neutral: 'text-slate-100',
  positive: 'text-emerald-400',
  warning: 'text-amber-400',
  danger: 'text-rose-400',
}

export function KpiCards() {
  const { data, loading, error } = useFetch(getDashboardSummary, [])

  if (loading) return <LoadingState label="Loading KPIs…" />
  if (error) return <ErrorState message={error} />
  if (!data) return null

  const kpis: Kpi[] = [
    { label: 'Revenue at Risk', value: formatMoney(data.revenue_at_risk_cents), tone: data.revenue_at_risk_cents > 0 ? 'warning' : 'neutral' },
    { label: 'Recovered Revenue', value: formatMoney(data.recovered_revenue_cents), tone: 'positive' },
    { label: 'Recovery Rate', value: formatPercent(data.recovery_rate), tone: 'neutral' },
    { label: 'Active Recovery Cases', value: String(data.active_recovery_cases), tone: 'neutral' },
    { label: 'Failed Payments', value: String(data.failed_payments), tone: 'neutral' },
    { label: 'Human Escalations', value: String(data.human_escalations), tone: data.human_escalations > 0 ? 'danger' : 'neutral' },
  ]

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {kpis.map((kpi) => (
        <Card key={kpi.label} className="!p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">{kpi.label}</p>
          <p className={`mt-1 text-2xl font-semibold tabular-nums ${TONE_STYLES[kpi.tone]}`}>{kpi.value}</p>
        </Card>
      ))}
    </div>
  )
}
