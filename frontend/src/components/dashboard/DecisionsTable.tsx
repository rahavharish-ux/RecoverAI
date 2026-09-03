import { getRecentDecisions } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, formatPercent, titleCase } from '../../lib/format'
import { DECISION_STATUS_TEXT } from '../../lib/theme'
import { Card } from '../ui/Card'
import { ModeBadge } from '../ui/ModeBadge'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

export function DecisionsTable({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const { data, loading, error } = useFetch(() => getRecentDecisions(15), [])

  return (
    <Card eyebrow="Decide" title="AI Recovery Decisions">
      {loading && <LoadingState label="Loading decisions…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && <EmptyState message="No agent decisions yet — run a scenario from the Demo Center." />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-faint">
                <th className="pb-2 pr-4 font-medium">Case</th>
                <th className="pb-2 pr-4 font-medium text-right">Amount at Risk</th>
                <th className="pb-2 pr-4 font-medium">Failure</th>
                <th className="pb-2 pr-4 font-medium text-right">Probability</th>
                <th className="pb-2 pr-4 font-medium">Selected Action</th>
                <th className="pb-2 pr-4 font-medium text-right">Expected Value</th>
                <th className="pb-2 pr-4 font-medium">Engine</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((d) => (
                <tr
                  key={d.decision_id}
                  role="button"
                  tabIndex={0}
                  aria-label={`Open case ${d.case_id}`}
                  className="cursor-pointer transition-colors duration-150 hover:bg-surface-hover focus-visible:bg-surface-hover"
                  onClick={() => onOpenCase(d.case_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onOpenCase(d.case_id)
                    }
                  }}
                >
                  <td className="py-2 pr-4 font-medium text-brand">#{d.case_id}</td>
                  <td className="py-2 pr-4 text-right tabular-nums text-muted">{formatMoney(d.amount_at_risk_cents)}</td>
                  <td className="py-2 pr-4 text-muted">{d.decline_code ? titleCase(d.decline_code) : '—'}</td>
                  <td className="py-2 pr-4 text-right tabular-nums text-muted">{formatPercent(d.recovery_probability)}</td>
                  <td className="py-2 pr-4 text-ink">{d.selected_action ? titleCase(d.selected_action) : 'No action'}</td>
                  <td className="py-2 pr-4 text-right tabular-nums text-muted">
                    {d.expected_value_cents !== null ? formatMoney(d.expected_value_cents) : '—'}
                  </td>
                  <td className="py-2 pr-4">
                    <ModeBadge agentMode={d.agent_mode} label={d.mode_label} />
                  </td>
                  <td className={`py-2 font-medium ${DECISION_STATUS_TEXT[d.status] ?? 'text-muted'}`}>{titleCase(d.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
