import { getRecentDecisions } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, formatPercent, titleCase } from '../../lib/format'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { ModeBadge } from '../ui/ModeBadge'

const STATUS_STYLES: Record<string, string> = {
  auto_approved: 'text-slate-400',
  executed: 'text-emerald-400',
  human_review: 'text-amber-400',
  rejected: 'text-rose-400',
  escalated: 'text-amber-400',
}

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
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 font-medium">Case</th>
                <th className="pb-2 font-medium text-right">Amount at Risk</th>
                <th className="pb-2 font-medium">Failure</th>
                <th className="pb-2 font-medium text-right">Probability</th>
                <th className="pb-2 font-medium">Selected Action</th>
                <th className="pb-2 font-medium text-right">Expected Value</th>
                <th className="pb-2 font-medium">Engine</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {data.map((d) => (
                <tr
                  key={d.decision_id}
                  role="button"
                  tabIndex={0}
                  aria-label={`Open case ${d.case_id}`}
                  className="cursor-pointer hover:bg-slate-800/40 focus-visible:bg-slate-800/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500"
                  onClick={() => onOpenCase(d.case_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onOpenCase(d.case_id)
                    }
                  }}
                >
                  <td className="py-2 font-medium text-violet-300">#{d.case_id}</td>
                  <td className="py-2 text-right tabular-nums text-slate-300">{formatMoney(d.amount_at_risk_cents)}</td>
                  <td className="py-2 text-slate-400">{d.decline_code ? titleCase(d.decline_code) : '—'}</td>
                  <td className="py-2 text-right tabular-nums text-slate-300">{formatPercent(d.recovery_probability)}</td>
                  <td className="py-2 text-slate-300">{d.selected_action ? titleCase(d.selected_action) : 'No action'}</td>
                  <td className="py-2 text-right tabular-nums text-slate-300">
                    {d.expected_value_cents !== null ? formatMoney(d.expected_value_cents) : '—'}
                  </td>
                  <td className="py-2">
                    <ModeBadge agentMode={d.agent_mode} label={d.mode_label} />
                  </td>
                  <td className={`py-2 ${STATUS_STYLES[d.status] ?? 'text-slate-400'}`}>{titleCase(d.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
