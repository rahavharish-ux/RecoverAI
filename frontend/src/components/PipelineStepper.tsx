import type { CaseEvent } from '../types/case'

type StageStatus = 'pending' | 'completed' | 'active' | 'blocked' | 'success'

interface Stage {
  label: string
  eventTypes: string[]
}

const STAGES: Stage[] = [
  { label: 'Detect', eventTypes: ['case_opened', 'payment_attempt_recorded'] },
  { label: 'Diagnose', eventTypes: ['diagnosed'] },
  { label: 'Predict', eventTypes: ['predicted'] },
  { label: 'Decide', eventTypes: ['policy_evaluated', 'agent_decided', 'agent_decision_reviewed'] },
  { label: 'Act', eventTypes: ['action_requested', 'action_rejected', 'action_executed'] },
  { label: 'Measure', eventTypes: ['action_outcome_recorded', 'case_resolved', 'case_escalated'] },
]
const DECIDE_INDEX = 3
const ACT_INDEX = 4
const MEASURE_INDEX = 5

const NODE_STYLES: Record<StageStatus, string> = {
  pending: 'border-line-strong bg-surface-2 text-faint',
  completed: 'border-brand bg-brand text-white',
  active: 'border-ai bg-ai/15 text-ai',
  blocked: 'border-danger bg-danger/15 text-danger',
  success: 'border-success bg-success text-white',
}

const LABEL_STYLES: Record<StageStatus, string> = {
  pending: 'text-faint',
  completed: 'text-ink',
  active: 'text-ai',
  blocked: 'text-danger',
  success: 'text-success',
}

const STATUS_CAPTION: Partial<Record<StageStatus, string>> = {
  active: 'Thinking…',
  blocked: 'Awaiting human review',
  success: 'Recovered',
}

function nodeGlyph(status: StageStatus, index: number): string {
  if (status === 'completed' || status === 'success') return '✓'
  if (status === 'blocked') return '⏸'
  if (status === 'active') return '·'
  return String(index + 1)
}

/** The "what happened, in order" story at a glance — WHY a payment
 * failed -> whether it CAN be recovered -> what ML/policy/the agent each
 * concluded -> what happened when it ran, ending in the always-on audit
 * ledger. Derived entirely from the same case_events the vertical
 * AuditTimeline renders in detail below, plus the live decision/case state
 * for the four visual states (completed / active-thinking / blocked-HITL /
 * success) — no invented data. */
export function PipelineStepper({
  events,
  busy = false,
  requiresHumanReview = false,
  resolved = false,
}: {
  events: CaseEvent[]
  busy?: boolean
  requiresHumanReview?: boolean
  resolved?: boolean
}) {
  const presentTypes = new Set(events.map((e) => e.event_type))
  const reached = STAGES.map((stage) => stage.eventTypes.some((t) => presentTypes.has(t)))
  const currentIndex = reached.lastIndexOf(true)
  const auditReached = events.length > 0

  const statuses: StageStatus[] = STAGES.map((_, i) => {
    if (i > currentIndex) return busy && i === currentIndex + 1 ? 'active' : 'pending'
    if (i < currentIndex) return 'completed'
    if (i === DECIDE_INDEX && requiresHumanReview && !reached[ACT_INDEX]) return 'blocked'
    if (i === MEASURE_INDEX && resolved) return 'success'
    return 'completed'
  })
  const allStatuses = [...statuses, auditReached ? 'completed' : 'pending'] as StageStatus[]
  const allLabels = [...STAGES.map((s) => s.label), 'Audit']

  return (
    <ol className="flex items-start">
      {allLabels.map((label, i) => {
        const status = allStatuses[i]
        const prevFilled = i === 0 ? true : allStatuses[i - 1] !== 'pending'
        const nextFilled = i < allStatuses.length - 1 && allStatuses[i + 1] !== 'pending'
        const caption = STATUS_CAPTION[status]
        return (
          <li key={label} className="flex flex-1 flex-col items-center text-center last:flex-none" aria-current={status !== 'pending' && i === currentIndex ? 'step' : undefined}>
            <div className="flex w-full items-center">
              <div className={`h-px flex-1 ${i === 0 ? 'invisible' : prevFilled ? 'bg-brand' : 'bg-line'}`} />
              <span
                title={caption ?? label}
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold transition-colors duration-150 ${NODE_STYLES[status]} ${
                  status === 'active' ? 'motion-safe:animate-pulse' : ''
                }`}
              >
                {nodeGlyph(status, i)}
              </span>
              <div className={`h-px flex-1 last:invisible ${nextFilled ? 'bg-brand' : 'bg-line'}`} />
            </div>
            <span className={`mt-1.5 max-w-[5.5rem] text-[10px] font-medium leading-tight ${LABEL_STYLES[status]}`}>{label}</span>
            {caption && <span className={`text-[9px] leading-tight ${LABEL_STYLES[status]}`}>{caption}</span>}
          </li>
        )
      })}
    </ol>
  )
}
