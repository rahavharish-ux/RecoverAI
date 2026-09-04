import { getDashboardSummary } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney } from '../../lib/format'
import { META_LABEL_CLASS } from '../../lib/theme'
import { Card } from '../ui/Card'
import { ErrorState, LoadingState } from '../ui/States'

/** The one raised surface on Overview. Revenue at risk — not recovered
 * revenue — is the hero: it's the number that's real and non-zero the
 * moment Detect ingests a failure, before any agent has acted, so the
 * screen has a strong resting state rather than leading with a ₹0.00
 * "recovered" figure that only means something after a demo has run. */
export function RevenueAtRiskHero() {
  const { data, loading, error } = useFetch(getDashboardSummary, [])

  if (loading) return <Card variant="raised"><LoadingState label="Loading…" /></Card>
  if (error) return <Card variant="raised"><ErrorState message={error} /></Card>
  if (!data) return null

  return (
    <Card variant="raised">
      <p className={META_LABEL_CLASS}>Revenue at risk</p>
      <p className="mt-1 text-4xl font-bold tabular-nums text-warning">{formatMoney(data.revenue_at_risk_cents)}</p>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
        <span>
          Recovered so far <strong className="tabular-nums text-success">{formatMoney(data.recovered_revenue_cents)}</strong>
        </span>
        <span>
          <strong className="tabular-nums text-ink">{data.active_recovery_cases}</strong> case
          {data.active_recovery_cases === 1 ? '' : 's'} currently active
        </span>
      </div>
    </Card>
  )
}
