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
              <tr className="text-[11px] uppercase tracking-wide text-faint">
                <th className="pb-2 pr-4 font-medium">Category</th>
                <th className="pb-2 pr-4 font-medium text-right">Cases</th>
                <th className="pb-2 pr-4 font-medium text-right">Amount at Risk</th>
                <th className="pb-2 pr-4 font-medium text-center">Retry Eligible</th>
                <th className="pb-2 pr-4 font-medium text-right">Recovered</th>
                <th className="pb-2 font-medium text-right">Escalated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((c) => (
                <tr key={c.decline_code}>
                  <td className="py-2 pr-4">
                    <p className="font-medium text-ink">{titleCase(c.decline_code)}</p>
                    <p className="text-xs text-faint">{c.decline_class}</p>
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums text-muted">{c.case_count}</td>
                  <td className="py-2 pr-4 text-right tabular-nums text-muted">{formatMoney(c.amount_involved_cents)}</td>
                  <td className="py-2 pr-4 text-center">
                    <span className={c.retry_eligible ? 'text-success' : 'text-faint'}>{c.retry_eligible ? '✓' : '—'}</span>
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums text-success">{c.resolved_count}</td>
                  <td className="py-2 text-right tabular-nums text-danger">{c.escalated_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
