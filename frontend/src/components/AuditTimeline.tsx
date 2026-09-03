import type { CaseEvent } from '../types/case'

const EVENT_LABELS: Record<string, string> = {
  case_opened: 'Failed',
  payment_attempt_recorded: 'Attempt Recorded',
  diagnosed: 'Diagnosed',
  predicted: 'Predicted',
  policy_evaluated: 'Policy Checked',
  agent_decided: 'Agent Decided',
  agent_decision_reviewed: 'Human Reviewed',
  action_requested: 'Action Requested',
  action_rejected: 'Action Rejected',
  action_executed: 'Action Executed',
  action_outcome_recorded: 'Outcome Recorded',
  case_escalated: 'Escalated',
  case_resolved: 'Recovered',
}

const NEGATIVE_EVENTS = new Set(['action_rejected', 'case_escalated'])
const POSITIVE_EVENTS = new Set(['case_resolved'])

function dotClass(eventType: string): string {
  if (POSITIVE_EVENTS.has(eventType)) return 'bg-emerald-400'
  if (NEGATIVE_EVENTS.has(eventType)) return 'bg-amber-400'
  return 'bg-slate-500'
}

export function AuditTimeline({ events }: { events: CaseEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-slate-500">No audit events recorded yet.</p>
  }

  return (
    <ol className="relative border-l border-slate-800 pl-5 space-y-4">
      {events.map((event) => (
        <li key={event.id} className="relative">
          <span
            className={`absolute -left-[26px] top-1 h-2.5 w-2.5 rounded-full ring-4 ring-slate-950 ${dotClass(event.event_type)}`}
          />
          <p className="text-sm font-medium text-slate-200">{EVENT_LABELS[event.event_type] ?? event.event_type}</p>
          <p className="text-xs text-slate-500">{event.summary}</p>
        </li>
      ))}
    </ol>
  )
}
