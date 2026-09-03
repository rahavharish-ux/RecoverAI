import type { CaseEvent } from '../types/case'

interface Stage {
  label: string
  eventTypes: string[]
}

const STAGES: Stage[] = [
  { label: 'Failure', eventTypes: ['case_opened'] },
  { label: 'Diagnosis', eventTypes: ['diagnosed'] },
  { label: 'ML Probability', eventTypes: ['predicted'] },
  { label: 'Policy Constraints', eventTypes: ['policy_evaluated'] },
  { label: 'Agent Decision', eventTypes: ['agent_decided'] },
  { label: 'Execution', eventTypes: ['action_executed'] },
  { label: 'Outcome', eventTypes: ['action_outcome_recorded', 'case_resolved', 'case_escalated'] },
  { label: 'Audit', eventTypes: [] }, // reached whenever any event exists — the trail itself
]

/** The "what happened, in order" story at a glance — WHY a payment
 * failed -> whether it CAN be recovered -> what ML/policy/the agent each
 * concluded -> what happened when it ran. Derived entirely from the same
 * case_events the vertical AuditTimeline renders in detail below; this is
 * just the headline view of the same real data. */
export function PipelineStepper({ events }: { events: CaseEvent[] }) {
  const presentTypes = new Set(events.map((e) => e.event_type))
  const reached = STAGES.map((stage) => (stage.eventTypes.length === 0 ? events.length > 0 : stage.eventTypes.some((t) => presentTypes.has(t))))
  const lastReachedIndex = reached.lastIndexOf(true)

  return (
    <ol className="flex items-start">
      {STAGES.map((stage, i) => {
        const isReached = reached[i]
        const isCurrent = i === lastReachedIndex
        return (
          <li key={stage.label} className="flex flex-1 flex-col items-center text-center last:flex-none">
            <div className="flex w-full items-center">
              <div className={`h-px flex-1 ${i === 0 ? 'invisible' : isReached ? 'bg-violet-500' : 'bg-slate-800'}`} />
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold ${
                  isCurrent
                    ? 'border-violet-400 bg-violet-500 text-white'
                    : isReached
                      ? 'border-violet-500/60 bg-violet-500/20 text-violet-300'
                      : 'border-slate-700 bg-slate-900 text-slate-600'
                }`}
              >
                {isReached ? '✓' : i + 1}
              </span>
              <div className={`h-px flex-1 last:invisible ${isReached && i !== STAGES.length - 1 && reached[i + 1] ? 'bg-violet-500' : 'bg-slate-800'}`} />
            </div>
            <span className={`mt-1.5 max-w-[5.5rem] text-[10px] leading-tight ${isReached ? 'text-slate-300' : 'text-slate-600'}`}>
              {stage.label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
