import { getPriorityCases } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, formatPercent, titleCase } from '../../lib/format'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

const RISK_STYLES: Record<string, string> = {
  low: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  high: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
}

export function PriorityQueue({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const { data, loading, error } = useFetch(() => getPriorityCases(10), [])

  return (
    <Card eyebrow="Triage" title="Priority Recovery Queue">
      {loading && <LoadingState label="Loading queue…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && <EmptyState message="No open cases right now." />}
      {data && data.length > 0 && (
        <ul className="space-y-2">
          {data.map((c) => (
            <li
              key={c.case_id}
              role="button"
              tabIndex={0}
              aria-label={`Open case ${c.case_id}`}
              onClick={() => onOpenCase(c.case_id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onOpenCase(c.case_id)
                }
              }}
              className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-slate-800 px-4 py-3 text-sm hover:bg-slate-800/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
            >
              <div className="flex items-center gap-3">
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium uppercase ${RISK_STYLES[c.risk_level]}`}>
                  {c.risk_level}
                </span>
                <div>
                  <p className="font-medium text-violet-300">Case #{c.case_id}</p>
                  <p className="text-xs text-slate-500">{c.decline_code ? titleCase(c.decline_code) : 'Undiagnosed'}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="tabular-nums text-slate-200">{formatMoney(c.amount_at_risk_cents)}</p>
                <p className="text-xs text-slate-500">
                  {formatPercent(c.recovery_probability)} probability
                  {c.requires_human_review && <span className="ml-1 text-amber-400">· review needed</span>}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
