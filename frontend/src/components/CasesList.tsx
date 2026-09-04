import { useState } from 'react'
import { listCases } from '../api/cases'
import { useFetch } from '../hooks/useFetch'
import { formatMoney } from '../lib/format'
import { CASE_STATUS_STYLES } from '../lib/theme'
import { Card } from './ui/Card'
import { EmptyState, ErrorState, LoadingState } from './ui/States'
import type { CaseStatus } from '../types/case'

export function CasesList({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'all'>('all')
  const { data, loading, error } = useFetch(() => listCases(statusFilter === 'all' ? undefined : statusFilter), [statusFilter])

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Recovery Cases</h1>
          <p className="mt-0.5 text-sm text-muted">Every case Detect has opened, filterable by current status.</p>
        </div>
        <div className="flex gap-1 text-xs">
          {(['all', 'open', 'escalated', 'resolved'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              aria-pressed={statusFilter === s}
              className={`rounded-full border px-3 py-1 font-medium capitalize transition-colors duration-150 ${
                statusFilter === s
                  ? 'border-brand/40 bg-brand/15 text-brand'
                  : 'border-line text-muted hover:text-ink'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </header>

      <Card>
        {loading && <LoadingState label="Loading cases…" />}
        {error && <ErrorState message={error} />}
        {data && data.length === 0 && (
          <EmptyState
            message={statusFilter === 'all' ? 'No cases yet.' : `No ${statusFilter} cases.`}
            action={
              statusFilter === 'all'
                ? { label: 'Run a scenario from the Demo Center' }
                : { label: 'Clear filter', onClick: () => setStatusFilter('all') }
            }
          />
        )}
        {data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-faint">
                  <th className="pb-2 pr-4 font-medium">Case</th>
                  <th className="pb-2 pr-4 font-medium text-right">Amount at Risk</th>
                  <th className="pb-2 pr-4 font-medium text-right">Recovered</th>
                  <th className="pb-2 pr-4 font-medium">Status</th>
                  <th className="pb-2 font-medium">Opened</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.map((c) => (
                  <tr
                    key={c.id}
                    role="button"
                    tabIndex={0}
                    aria-label={`Open case ${c.id}`}
                    onClick={() => onOpenCase(c.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onOpenCase(c.id)
                      }
                    }}
                    className="cursor-pointer transition-colors duration-150 hover:bg-surface-hover focus-visible:bg-surface-hover"
                  >
                    <td className="py-2 pr-4 font-medium text-brand">#{c.id}</td>
                    <td className="py-2 pr-4 text-right tabular-nums text-muted">{formatMoney(c.amount_at_risk_cents)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums text-muted">{formatMoney(c.amount_recovered_cents)}</td>
                    <td className="py-2 pr-4">
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium uppercase ${CASE_STATUS_STYLES[c.status]}`}>
                        {c.status}
                      </span>
                    </td>
                    <td className="py-2 text-faint">{new Date(c.opened_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {data && data.length > 0 && <p className="text-xs text-faint">{data.length} case(s) shown.</p>}
    </div>
  )
}
