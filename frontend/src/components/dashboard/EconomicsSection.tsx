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
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: 'Revenue at Risk', value: data.revenue_at_risk_cents, tone: 'text-amber-400' },
              { label: 'Potential Recoverable', value: data.potential_recoverable_cents, tone: 'text-violet-300' },
              { label: 'Recovered Revenue', value: data.recovered_revenue_cents, tone: 'text-emerald-400' },
              { label: 'Net Recovery Value', value: data.net_recovery_value_cents, tone: 'text-emerald-400' },
            ].map((item) => (
              <div key={item.label}>
                <p className="text-xs uppercase tracking-wide text-slate-500">{item.label}</p>
                <p className={`text-lg font-semibold tabular-nums ${item.tone}`}>{formatMoney(item.value)}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 border-t border-slate-800 pt-4 sm:grid-cols-4 text-sm">
            <div>
              <p className="text-xs text-slate-500">Recovery Attempts</p>
              <p className="tabular-nums text-slate-200">{data.recovery_attempts}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Successful Recoveries</p>
              <p className="tabular-nums text-slate-200">{data.successful_recoveries}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Human Escalations</p>
              <p className="tabular-nums text-slate-200">{data.human_escalations}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Action Cost</p>
              <p className="tabular-nums text-slate-200">{formatMoney(data.action_cost_cents)}</p>
            </div>
          </div>
          <p className="text-xs text-slate-600">{data.note}</p>
        </div>
      )}
    </Card>
  )
}
