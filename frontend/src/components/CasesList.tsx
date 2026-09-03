import { useState } from 'react'
import { listCases } from '../api/cases'
import { useFetch } from '../hooks/useFetch'
import { formatMoney } from '../lib/format'
import { Card } from './ui/Card'
import { EmptyState, ErrorState, LoadingState } from './ui/States'
import type { CaseStatus } from '../types/case'

const STATUS_STYLES: Record<CaseStatus, string> = {
  open: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  escalated: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  resolved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
}

export function CasesList({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'all'>('all')
  const { data, loading, error } = useFetch(() => listCases(statusFilter === 'all' ? undefined : statusFilter), [statusFilter])

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Cases</h1>
        <div className="flex gap-1 text-xs">
          {(['all', 'open', 'escalated', 'resolved'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              aria-pressed={statusFilter === s}
              className={`rounded-full border px-3 py-1 font-medium capitalize focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500 ${
                statusFilter === s
                  ? 'border-violet-500/40 bg-violet-500/15 text-violet-300'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200'
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
        {data && data.length === 0 && <EmptyState message="No cases match this filter." />}
        {data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-slate-500">
                  <th className="pb-2 font-medium">Case</th>
                  <th className="pb-2 font-medium text-right">Amount at Risk</th>
                  <th className="pb-2 font-medium text-right">Recovered</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Opened</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
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
                    className="cursor-pointer hover:bg-slate-800/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
                  >
                    <td className="py-2 font-medium text-violet-300">#{c.id}</td>
                    <td className="py-2 text-right tabular-nums text-slate-300">{formatMoney(c.amount_at_risk_cents, c.currency)}</td>
                    <td className="py-2 text-right tabular-nums text-slate-300">{formatMoney(c.amount_recovered_cents, c.currency)}</td>
                    <td className="py-2">
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium uppercase ${STATUS_STYLES[c.status]}`}>
                        {c.status}
                      </span>
                    </td>
                    <td className="py-2 text-slate-500">{new Date(c.opened_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {data && data.length > 0 && <p className="text-xs text-slate-600">{data.length} case(s) shown.</p>}
    </div>
  )
}
