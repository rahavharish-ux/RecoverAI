import { getFailureCategories } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, titleCase } from '../../lib/format'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

export function FailureIntelligence() {
  const { data, loading, error } = useFetch(getFailureCategories, [])

  return (
    <Card eyebrow="Diagnose" title="Failure Intelligence">
      {loading && <LoadingState label="Loading failure categories…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && <EmptyState message="No diagnosed failures yet." />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 font-medium">Category</th>
                <th className="pb-2 font-medium text-right">Cases</th>
                <th className="pb-2 font-medium text-right">Amount at Risk</th>
                <th className="pb-2 font-medium text-center">Retry Eligible</th>
                <th className="pb-2 font-medium text-right">Recovered</th>
                <th className="pb-2 font-medium text-right">Escalated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {data.map((c) => (
                <tr key={c.decline_code}>
                  <td className="py-2">
                    <p className="font-medium text-slate-200">{titleCase(c.decline_code)}</p>
                    <p className="text-xs text-slate-500">{c.decline_class}</p>
                  </td>
                  <td className="py-2 text-right tabular-nums text-slate-300">{c.case_count}</td>
                  <td className="py-2 text-right tabular-nums text-slate-300">{formatMoney(c.amount_involved_cents)}</td>
                  <td className="py-2 text-center">
                    <span className={c.retry_eligible ? 'text-emerald-400' : 'text-slate-600'}>
                      {c.retry_eligible ? '✓' : '—'}
                    </span>
                  </td>
                  <td className="py-2 text-right tabular-nums text-emerald-400">{c.resolved_count}</td>
                  <td className="py-2 text-right tabular-nums text-amber-400">{c.escalated_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
