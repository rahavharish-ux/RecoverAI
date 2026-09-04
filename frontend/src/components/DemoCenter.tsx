import { useState } from 'react'
import { runDemoScenario } from '../api/demo'
import { formatMoney, formatPercent, titleCase } from '../lib/format'
import { NEUTRAL_TAG_STYLES } from '../lib/theme'
import { Card } from './ui/Card'

type Tag = 'RECOVERY' | 'SAFETY' | 'POLICY' | 'HITL' | 'EDGE CASE'

// These are taxonomy labels, not live payment or decision states — none
// of them earn a hue. Real money/decision states (recovered, failed,
// pending human review) already carry color elsewhere in the app;
// reusing that same color language here for a classification tag would
// make "this scenario is about HITL" look indistinguishable from "this
// case actually failed." Distinguished by text only, on purpose.
const TAG_STYLES: Record<Tag, string> = {
  RECOVERY: NEUTRAL_TAG_STYLES,
  SAFETY: NEUTRAL_TAG_STYLES,
  POLICY: NEUTRAL_TAG_STYLES,
  HITL: NEUTRAL_TAG_STYLES,
  'EDGE CASE': NEUTRAL_TAG_STYLES,
}

interface Scenario {
  id: string
  title: string
  description: string
  tags: Tag[]
  action: string
  expectedOutcome: string
}

// Purely descriptive, display-only metadata — the backend
// (app/services/demo_service.py::DEMO_SCENARIOS) is the single source of
// truth for each scenario's decline code, amount, and isolated fixture;
// the frontend no longer hardcodes an invoice/payment-method id and calls
// the backend by scenario id alone (see runDemoScenario, api/demo.ts).
const SCENARIOS: Scenario[] = [
  {
    id: 'A',
    title: 'Successful Recovery',
    description: 'A transient processor error with a high recovery probability — the agent retries automatically.',
    tags: ['RECOVERY'],
    action: 'Retry Payment',
    expectedOutcome: 'Recovered',
  },
  {
    id: 'B',
    title: 'Fraud → Human Review',
    description: 'A fraud signal — the agent can only escalate, and nothing executes without human approval.',
    tags: ['SAFETY', 'HITL'],
    action: 'Escalate',
    expectedOutcome: 'Blocked pending human approval',
  },
  {
    id: 'C',
    title: 'Expired Card → Method Update',
    description: 'An expired card — retry is never offered by policy; the agent requests a method update instead.',
    tags: ['POLICY'],
    action: 'Request Method Update',
    expectedOutcome: 'Method-update request sent',
  },
  {
    id: 'D',
    title: 'Retry & Cooldown Protection',
    description:
      'After one retry, a second attempt this soon is blocked by the cooldown window — the agent adapts and re-decides rather than retrying blindly.',
    tags: ['SAFETY', 'POLICY'],
    action: 'Retry, then re-decide',
    expectedOutcome: 'Second retry correctly blocked',
  },
  {
    id: 'E',
    title: 'High Value → Human Review',
    description: 'A larger transaction crosses the human-review threshold even though retry looks safe.',
    tags: ['HITL', 'EDGE CASE'],
    action: 'Retry (proposed)',
    expectedOutcome: 'Blocked pending human approval',
  },
]

interface StepLog {
  label: string
  detail: string
  tone: 'neutral' | 'positive' | 'warning' | 'danger'
}

const TONE_STYLES: Record<StepLog['tone'], string> = {
  neutral: 'border-line bg-surface-2',
  positive: 'border-success/30 bg-success/10',
  warning: 'border-warning/30 bg-warning/10',
  danger: 'border-danger/30 bg-danger/10',
}

export function DemoCenter({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const [running, setRunning] = useState<string | null>(null)
  const [log, setLog] = useState<StepLog[]>([])
  const [resultCaseId, setResultCaseId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function runScenario(scenario: Scenario) {
    setRunning(scenario.id)
    setLog([])
    setError(null)
    setResultCaseId(null)
    try {
      // One real backend call runs the whole pipeline — DETECT through ACT
      // and AUDIT — against a freshly created, isolated demo case; nothing
      // below is invented client-side, it only formats what came back.
      const result = await runDemoScenario(scenario.id)
      const caseId = result.ingest.case.id
      setResultCaseId(caseId)

      const entries: StepLog[] = [
        {
          label: 'Payment Failed',
          detail: `Case #${caseId} opened — ${result.ingest.diagnosis?.explanation ?? 'diagnosis pending'}`,
          tone: 'neutral',
        },
      ]

      if (result.ingest.prediction) {
        entries.push({
          label: 'Recovery Predicted',
          detail: `${formatPercent(result.ingest.prediction.recovery_probability)} probability (${result.ingest.prediction.confidence_band} confidence)`,
          tone: 'neutral',
        })
      }

      entries.push({
        label: 'Agent Decided',
        detail: `[${result.decision.mode_label}] ${result.decision.reasoning_summary}`,
        tone: 'neutral',
      })

      if (result.decision.status === 'human_review') {
        entries.push({
          label: 'Human Review Required',
          detail: `Risk flags: ${result.decision.risk_flags.map(titleCase).join(', ') || 'none'} — autonomous execution is blocked until a human approves.`,
          tone: 'warning',
        })
        setLog(entries)
        return
      }

      const executed = result.execute
      if (executed?.outcome) {
        const succeeded = executed.outcome.result === 'succeeded'
        entries.push({
          label: succeeded ? 'Payment Recovered' : 'Retry Failed',
          detail: succeeded
            ? `${formatMoney(executed.outcome.amount_recovered_cents)} recovered.`
            : 'The retry did not succeed this time — the case remains open for further action.',
          tone: succeeded ? 'positive' : 'warning',
        })
      } else if (executed?.action) {
        entries.push({ label: 'Action Executed', detail: `${titleCase(executed.action.action_type)} completed.`, tone: 'neutral' })
      }

      if (result.second_decision) {
        entries.push({
          label: 'Second Decision — Protection Check',
          detail: `[${result.second_decision.mode_label}] ${result.second_decision.reasoning_summary}`,
          tone: 'neutral',
        })
      }

      setLog(entries)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scenario failed to run.')
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">RecoverAI</p>
        <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink">Demo Center</h1>
        <p className="mt-0.5 max-w-2xl text-sm text-muted">
          Each scenario runs the real pipeline through the real API — nothing here is scripted UI. Failures and
          retries route through the same simulated gateway as everything else in the sandbox.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SCENARIOS.map((s) => (
          <Card key={s.id} className="flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-brand">Scenario {s.id}</p>
                <div className="flex flex-wrap justify-end gap-1">
                  {s.tags.map((tag) => (
                    <span
                      key={tag}
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${TAG_STYLES[tag]}`}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <h3 className="mt-1.5 text-sm font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-xs text-muted">{s.description}</p>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2 text-[11px] text-faint">
                <span>
                  Action: <span className="text-muted">{s.action}</span>
                </span>
                <span>
                  Expected: <span className="text-muted">{s.expectedOutcome}</span>
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void runScenario(s)}
              disabled={running !== null}
              className="mt-4 rounded-md bg-brand px-3 py-2 text-xs font-medium text-white transition-colors duration-150 hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-40"
            >
              {running === s.id ? 'Running…' : 'Run Scenario'}
            </button>
          </Card>
        ))}
      </div>

      {(log.length > 0 || error) && (
        <Card eyebrow="Live Result" title="Scenario Lifecycle">
          {error && <p className="mb-3 text-sm text-danger">{error}</p>}
          <ol className="space-y-2">
            {log.map((step, i) => (
              <li key={i} className={`rounded-lg border px-4 py-2.5 text-sm ${TONE_STYLES[step.tone]}`}>
                <p className="font-medium text-ink">{step.label}</p>
                <p className="text-xs text-muted">{step.detail}</p>
              </li>
            ))}
          </ol>
          {resultCaseId !== null && (
            <button
              type="button"
              onClick={() => onOpenCase(resultCaseId)}
              className="mt-4 rounded-md border border-line-strong px-3 py-2 text-xs font-medium text-ink transition-colors duration-150 hover:bg-surface-hover"
            >
              View Case Intelligence →
            </button>
          )}
        </Card>
      )}
    </div>
  )
}
