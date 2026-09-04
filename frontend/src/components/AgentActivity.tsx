import { getRecentDecisions } from '../api/dashboard'
import { useFetch } from '../hooks/useFetch'
import { formatMoney, formatPercent, titleCase } from '../lib/format'
import { RISK_FLAG_STYLES, riskFlagTone } from '../lib/theme'
import { Card } from './ui/Card'
import { ModeBadge } from './ui/ModeBadge'
import { EmptyState, ErrorState, LoadingState } from './ui/States'

const STATUS_LABEL: Record<string, string> = {
  auto_approved: 'Auto-approved',
  executed: 'Executed',
  human_review: 'Awaiting human review',
  rejected: 'Rejected by reviewer',
  escalated: 'Escalated',
}

export function AgentActivity({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const { data, loading, error } = useFetch(() => getRecentDecisions(30), [])

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Agent Activity</h1>
        <p className="mt-0.5 text-sm text-muted">
          Every decision the agent has made — diagnosis, prediction, policy validation, and the resulting choice —
          across all cases, most recent first. Full tool-call detail for one case lives on its Case Intelligence page.
        </p>
      </header>

      <Card>
        {loading && <LoadingState label="Loading activity…" />}
        {error && <ErrorState message={error} />}
        {data && data.length === 0 && (
          <EmptyState message="No agent activity yet." action={{ label: 'Run a scenario from the Demo Center' }} />
        )}
        {data && data.length > 0 && (
          <ol className="relative space-y-5 border-l border-line pl-5">
            {data.map((d) => (
              <li key={d.decision_id} className="relative">
                <span className="absolute -left-[25px] top-1 h-2 w-2 rounded-full bg-line-strong ring-4 ring-surface" />
                <div className="flex flex-wrap items-center gap-2 text-xs text-faint">
                  <button
                    type="button"
                    onClick={() => onOpenCase(d.case_id)}
                    className="rounded font-medium text-brand hover:underline"
                  >
                    Case #{d.case_id}
                  </button>
                  <span>·</span>
                  <span>{d.decline_code ? titleCase(d.decline_code) : 'Undiagnosed'}</span>
                  <span>·</span>
                  <span>{formatMoney(d.amount_at_risk_cents)} at risk</span>
                  <span>·</span>
                  <time dateTime={d.decided_at}>{new Date(d.decided_at).toLocaleString()}</time>
                </div>
                <p className="mt-1 text-sm text-ink">
                  {d.selected_action ? (
                    <>
                      Selected <span className="font-medium">{titleCase(d.selected_action)}</span>
                      {d.recovery_probability !== null && <> — {formatPercent(d.recovery_probability)} recovery probability</>}
                    </>
                  ) : (
                    'Found no safe automated action'
                  )}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <ModeBadge agentMode={d.agent_mode} label={d.mode_label} />
                  <span className="text-xs text-faint">{STATUS_LABEL[d.status] ?? titleCase(d.status)}</span>
                  {d.risk_flags.map((flag) => (
                    <span
                      key={flag}
                      className={`rounded-full border px-2 py-0.5 text-xs ${RISK_FLAG_STYLES[riskFlagTone(flag)]}`}
                    >
                      {titleCase(flag)}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  )
}
