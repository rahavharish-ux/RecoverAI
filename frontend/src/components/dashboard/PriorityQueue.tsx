import { getPriorityCases } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, formatPercent, titleCase } from '../../lib/format'
import { RISK_LEVEL_STYLES } from '../../lib/theme'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

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
              className="flex cursor-pointer items-center justify-between gap-3 rounded-md border border-line px-4 py-3 text-sm transition-colors duration-150 hover:bg-surface-hover focus-visible:bg-surface-hover"
            >
              <div className="flex items-center gap-3">
                <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase ${RISK_LEVEL_STYLES[c.risk_level]}`}>
                  {c.risk_level}
                </span>
                <div>
                  <p className="font-medium text-brand">Case #{c.case_id}</p>
                  <p className="text-xs text-faint">{c.decline_code ? titleCase(c.decline_code) : 'Undiagnosed'}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="tabular-nums text-ink">{formatMoney(c.amount_at_risk_cents)}</p>
                <p className="text-xs text-faint">
                  {formatPercent(c.recovery_probability)} probability
                  {c.requires_human_review && <span className="ml-1 text-danger">· review needed</span>}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
