import { getEconomics } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney } from '../../lib/format'
import { Card } from '../ui/Card'
import { ErrorState, LoadingState } from '../ui/States'

export function EconomicsSection() {
  const { data, loading, error } = useFetch(getEconomics, [])

  return (
    <Card eyebrow="Measure" title="Recovery Economics">
      {loading && <LoadingState label="Loading economics…" />}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: 'Revenue at Risk', value: data.revenue_at_risk_cents, tone: 'text-warning' },
              { label: 'Potential Recoverable', value: data.potential_recoverable_cents, tone: 'text-ai' },
              { label: 'Recovered Revenue', value: data.recovered_revenue_cents, tone: 'text-success' },
              { label: 'Net Recovery Value', value: data.net_recovery_value_cents, tone: 'text-success' },
            ].map((item) => (
              <div key={item.label}>
                <p className="text-[11px] font-medium uppercase tracking-wide text-faint">{item.label}</p>
                <p className={`text-lg font-bold tabular-nums ${item.tone}`}>{formatMoney(item.value)}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-faint">Recovery Attempts</p>
              <p className="tabular-nums text-ink">{data.recovery_attempts}</p>
            </div>
            <div>
              <p className="text-xs text-faint">Successful Recoveries</p>
              <p className="tabular-nums text-ink">{data.successful_recoveries}</p>
            </div>
            <div>
              <p className="text-xs text-faint">Human Escalations</p>
              <p className="tabular-nums text-ink">{data.human_escalations}</p>
            </div>
            <div>
              <p className="text-xs text-faint">Action Cost</p>
              <p className="tabular-nums text-ink">{formatMoney(data.action_cost_cents)}</p>
            </div>
          </div>
          <p className="text-xs text-faint">{data.note}</p>
        </div>
      )}
    </Card>
  )
}
