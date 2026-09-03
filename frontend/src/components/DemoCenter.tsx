import { useState } from 'react'
import { executeAgentDecision, runAgentDecision } from '../api/cases'
import { ingestPaymentAttempt } from '../api/demo'
import { formatMoney, formatPercent, titleCase } from '../lib/format'
import { Card } from './ui/Card'

interface Scenario {
  id: string
  title: string
  description: string
  invoiceId: number
  paymentMethodId: number
  declineCode: string
  amountCents: number
}

const SCENARIOS: Scenario[] = [
  {
    id: 'A',
    title: 'Successful Recovery',
    description: 'A transient processor error with a high recovery probability — the agent retries automatically.',
    invoiceId: 1,
    paymentMethodId: 1,
    declineCode: 'processor_error',
    amountCents: 2900,
  },
  {
    id: 'B',
    title: 'Fraud → Human Review',
    description: 'A fraud signal — the agent can only escalate, and nothing executes without human approval.',
    invoiceId: 2,
    paymentMethodId: 2,
    declineCode: 'fraud_suspected',
    amountCents: 1900,
  },
  {
    id: 'C',
    title: 'Expired Card → Method Update',
    description: 'An expired card — retry is never offered by policy; the agent requests a method update instead.',
    invoiceId: 4,
    paymentMethodId: 4,
    declineCode: 'expired_card',
    amountCents: 4900,
  },
  {
    id: 'D',
    title: 'Retry & Cooldown Protection',
    description:
      'After one retry, a second attempt this soon is blocked by the cooldown window — the agent adapts and re-decides rather than retrying blindly.',
    invoiceId: 1,
    paymentMethodId: 1,
    declineCode: 'insufficient_funds',
    amountCents: 2900,
  },
  {
    id: 'E',
    title: 'High Value → Human Review',
    description: 'A larger transaction crosses the human-review threshold even though retry looks safe.',
    invoiceId: 3,
    paymentMethodId: 3,
    declineCode: 'card_declined',
    amountCents: 19900,
  },
]

interface StepLog {
  label: string
  detail: string
  tone: 'neutral' | 'positive' | 'warning' | 'danger'
}

const TONE_STYLES: Record<StepLog['tone'], string> = {
  neutral: 'border-slate-800 bg-slate-900',
  positive: 'border-emerald-500/30 bg-emerald-500/10',
  warning: 'border-amber-500/30 bg-amber-500/10',
  danger: 'border-rose-500/30 bg-rose-500/10',
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
      const ingest = await ingestPaymentAttempt({
        invoiceId: scenario.invoiceId,
        paymentMethodId: scenario.paymentMethodId,
        amountCents: scenario.amountCents,
        declineCode: scenario.declineCode,
      })
      const caseId = ingest.case.id
      setResultCaseId(caseId)
      setLog((l) => [
        ...l,
        {
          label: 'Payment Failed',
          detail: `Case #${caseId} opened — ${ingest.diagnosis?.explanation ?? 'diagnosis pending'}`,
          tone: 'neutral',
        },
      ])
      if (ingest.prediction) {
        setLog((l) => [
          ...l,
          {
            label: 'Recovery Predicted',
            detail: `${formatPercent(ingest.prediction!.recovery_probability)} probability (${ingest.prediction!.confidence_band} confidence)`,
            tone: 'neutral',
          },
        ])
      }

      const decision = await runAgentDecision(caseId)
      setLog((l) => [
        ...l,
        {
          label: 'Agent Decided',
          detail: `[${decision.mode_label}] ${decision.reasoning_summary}`,
          tone: 'neutral',
        },
      ])

      if (decision.status === 'human_review') {
        setLog((l) => [
          ...l,
          {
            label: 'Human Review Required',
            detail: `Risk flags: ${decision.risk_flags.map(titleCase).join(', ') || 'none'} — autonomous execution is blocked until a human approves.`,
            tone: 'warning',
          },
        ])
        return
      }

      const executed = await executeAgentDecision(caseId)
      if (executed.outcome) {
        const succeeded = executed.outcome.result === 'succeeded'
        setLog((l) => [
          ...l,
          {
            label: succeeded ? 'Payment Recovered' : 'Retry Failed',
            detail: succeeded
              ? `${formatMoney(executed.outcome!.amount_recovered_cents)} recovered.`
              : 'The retry did not succeed this time — the case remains open for further action.',
            tone: succeeded ? 'positive' : 'warning',
          },
        ])
      } else if (executed.action) {
        setLog((l) => [
          ...l,
          { label: 'Action Executed', detail: `${titleCase(executed.action!.action_type)} completed.`, tone: 'neutral' },
        ])
      }

      if (scenario.id === 'D' && executed.case.status === 'open') {
        const secondDecision = await runAgentDecision(caseId)
        setLog((l) => [
          ...l,
          {
            label: 'Second Decision — Protection Check',
            detail: `[${secondDecision.mode_label}] ${secondDecision.reasoning_summary}`,
            tone: 'neutral',
          },
        ])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scenario failed to run.')
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Demo Center</h1>
        <p className="text-sm text-slate-500">
          Each scenario runs the real pipeline through the real API — nothing here is scripted UI. Failures and
          retries route through the same simulated gateway as everything else in the sandbox.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SCENARIOS.map((s) => (
          <Card key={s.id} className="flex flex-col justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-violet-400">Scenario {s.id}</p>
              <h3 className="mt-1 text-sm font-semibold text-slate-100">{s.title}</h3>
              <p className="mt-1 text-xs text-slate-500">{s.description}</p>
            </div>
            <button
              type="button"
              onClick={() => void runScenario(s)}
              disabled={running !== null}
              className="mt-4 rounded-md bg-violet-600 px-3 py-2 text-xs font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {running === s.id ? 'Running…' : 'Run Scenario'}
            </button>
          </Card>
        ))}
      </div>

      {(log.length > 0 || error) && (
        <Card eyebrow="Live Result" title="Scenario Lifecycle">
          {error && <p className="mb-3 text-sm text-rose-400">{error}</p>}
          <ol className="space-y-2">
            {log.map((step, i) => (
              <li key={i} className={`rounded-lg border px-4 py-2.5 text-sm ${TONE_STYLES[step.tone]}`}>
                <p className="font-medium text-slate-200">{step.label}</p>
                <p className="text-xs text-slate-400">{step.detail}</p>
              </li>
            ))}
          </ol>
          {resultCaseId !== null && (
            <button
              type="button"
              onClick={() => onOpenCase(resultCaseId)}
              className="mt-4 rounded-md border border-slate-700 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800"
            >
              View Case Intelligence →
            </button>
          )}
        </Card>
      )}
    </div>
  )
}
