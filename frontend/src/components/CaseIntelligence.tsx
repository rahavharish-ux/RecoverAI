import { useCallback, useEffect, useState } from 'react'
import {
  executeAgentDecision,
  getCase,
  getCaseActions,
  getCaseEvents,
  getLatestDecision,
  runAgentDecision,
} from '../api/cases'
import type { AgentDecision, CaseAction, CaseEvent, CaseSummary } from '../types/case'
import { AuditTimeline } from './AuditTimeline'

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  escalated: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  resolved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
}

const BAND_STYLES: Record<string, string> = {
  high: 'text-emerald-400',
  medium: 'text-amber-400',
  low: 'text-slate-400',
}

const MODE_BADGE_STYLES: Record<string, string> = {
  llm: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  deterministic: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
}

function confidenceBand(probability: number | null): 'low' | 'medium' | 'high' {
  if (probability === null) return 'low'
  if (probability >= 0.66) return 'high'
  if (probability >= 0.33) return 'medium'
  return 'low'
}

function formatMoney(cents: number, currency: string): string {
  try {
    return (cents / 100).toLocaleString(undefined, { style: 'currency', currency: currency.toUpperCase() })
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`
  }
}

function friendlyReasonCode(code: string): string {
  return code.replaceAll('_', ' ')
}

interface CaseData {
  summary: CaseSummary
  events: CaseEvent[]
  decision: AgentDecision | null
  actions: CaseAction[]
}

async function loadCase(caseId: number): Promise<CaseData | null> {
  const summary = await getCase(caseId)
  if (!summary) return null
  const [events, decision, actions] = await Promise.all([
    getCaseEvents(caseId),
    getLatestDecision(caseId),
    getCaseActions(caseId),
  ])
  return { summary, events, decision, actions }
}

export function CaseIntelligence({ initialCaseId = 1 }: { initialCaseId?: number }) {
  const [caseId, setCaseId] = useState(initialCaseId)
  const [caseIdInput, setCaseIdInput] = useState(String(initialCaseId))
  const [data, setData] = useState<CaseData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    try {
      const result = await loadCase(id)
      setData(result)
      if (result === null) setError(`Case #${id} was not found.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load case.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh(caseId)
  }, [caseId, refresh])

  const handleDecide = async () => {
    setBusy(true)
    setError(null)
    try {
      await runAgentDecision(caseId)
      await refresh(caseId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent decision failed.')
    } finally {
      setBusy(false)
    }
  }

  const handleExecute = async () => {
    setBusy(true)
    setError(null)
    try {
      await executeAgentDecision(caseId)
      await refresh(caseId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Execution failed.')
    } finally {
      setBusy(false)
    }
  }

  const executedAction = data?.actions.find((a) => a.id === data.decision?.executed_action_id) ?? null
  const latestDiagnosis = data?.events.filter((e) => e.event_type === 'diagnosed').at(-1) ?? null
  const declineCode = (latestDiagnosis?.details.decline_code as string | undefined) ?? null

  return (
    <div className="min-h-svh bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-2xl px-6 py-10">
        <header className="mb-8 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">RecoverAI</p>
            <h1 className="text-2xl font-semibold tracking-tight">Case Intelligence</h1>
          </div>
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              const parsed = Number.parseInt(caseIdInput, 10)
              if (Number.isFinite(parsed) && parsed > 0) setCaseId(parsed)
            }}
          >
            <label htmlFor="case-id" className="text-xs text-slate-500">
              Case #
            </label>
            <input
              id="case-id"
              value={caseIdInput}
              onChange={(e) => setCaseIdInput(e.target.value)}
              className="w-16 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm tabular-nums focus:border-violet-500 focus:outline-none"
            />
          </form>
        </header>

        {loading && <p className="text-sm text-slate-500">Loading case…</p>}
        {error && !loading && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>
        )}

        {data && !loading && (
          <div className="space-y-8">
            {/* Transaction */}
            <section>
              <p className="text-xs uppercase tracking-wide text-slate-500">Transaction</p>
              <p className="text-4xl font-semibold tabular-nums">
                {formatMoney(data.summary.amount_at_risk_cents || data.summary.amount_recovered_cents, data.summary.currency)}
              </p>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase ${STATUS_STYLES[data.summary.status]}`}
                >
                  {data.summary.status}
                </span>
                {declineCode && (
                  <span className="text-xs text-slate-500">Failure: {friendlyReasonCode(declineCode)}</span>
                )}
              </div>
            </section>

            {/* Prediction */}
            {data.decision && data.decision.recovery_probability !== null && (
              <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                <p className="text-xs uppercase tracking-wide text-slate-500 mb-3">AI Recovery Prediction</p>
                <div className="flex items-baseline gap-3">
                  <span className="text-5xl font-bold tabular-nums">
                    {Math.round(data.decision.recovery_probability * 100)}%
                  </span>
                  <span className={`text-sm font-semibold uppercase ${BAND_STYLES[confidenceBand(data.decision.recovery_probability)]}`}>
                    {confidenceBand(data.decision.recovery_probability)} confidence
                  </span>
                </div>
              </section>
            )}

            {/* Available actions */}
            {data.decision && (
              <section>
                <p className="text-xs uppercase tracking-wide text-slate-500 mb-3">Available Actions</p>
                <ul className="space-y-2">
                  {data.decision.available_actions.map((action) => {
                    const isSelected = action.action_type === data.decision?.selected_action
                    return (
                      <li
                        key={action.action_type}
                        className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
                          isSelected ? 'border-violet-500/40 bg-violet-500/10' : 'border-slate-800 bg-slate-900'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <span className={isSelected ? 'text-violet-400' : 'text-slate-500'}>{isSelected ? '✓' : '○'}</span>
                          <span className="capitalize">{action.action_type.replaceAll('_', ' ')}</span>
                        </span>
                        <span className="tabular-nums text-slate-400">
                          {formatMoney(action.expected_value_cents, data.summary.currency)}
                        </span>
                      </li>
                    )
                  })}
                  {data.decision.available_actions.length === 0 && (
                    <li className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
                      <span>⚠</span>
                      <span>No automated action is currently allowed — human escalation required.</span>
                    </li>
                  )}
                </ul>
              </section>
            )}

            {/* Agent decision */}
            {data.decision && (
              <section>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide text-slate-500">Agent Decision</p>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${MODE_BADGE_STYLES[data.decision.agent_mode]}`}
                  >
                    {data.decision.mode_label}
                  </span>
                </div>
                <blockquote className="rounded-lg border-l-2 border-violet-500/50 bg-slate-900 px-4 py-3 text-sm text-slate-300 italic">
                    “{data.decision.reasoning_summary}”
                </blockquote>
                <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-slate-500">
                  <span>Confidence: {Math.round(data.decision.confidence * 100)}%</span>
                  {data.decision.status !== 'human_review' && (
                    <span className="flex items-center gap-1 text-emerald-400">
                      <span>✓</span> Policy validation passed
                    </span>
                  )}
                  {data.decision.status === 'human_review' && (
                    <span className="flex items-center gap-1 text-amber-400">
                      <span>⚠</span> Human review required
                      {data.decision.risk_flags.length > 0 && (
                        <span className="text-slate-500">({data.decision.risk_flags.map(friendlyReasonCode).join(', ')})</span>
                      )}
                    </span>
                  )}
                </div>
              </section>
            )}

            {/* Action result */}
            {executedAction && (
              <section
                className={`rounded-lg border px-4 py-3 text-sm ${
                  data.summary.status === 'resolved'
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                    : 'border-slate-800 bg-slate-900 text-slate-300'
                }`}
              >
                <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Action Result</p>
                {data.summary.status === 'resolved' ? (
                  <p>Recovery successful — {formatMoney(data.summary.amount_recovered_cents, data.summary.currency)} recovered.</p>
                ) : (
                  <p>{executedAction.action_type.replaceAll('_', ' ')} executed — case remains {data.summary.status}.</p>
                )}
              </section>
            )}

            {/* Controls */}
            <section className="flex gap-3">
              <button
                type="button"
                onClick={handleDecide}
                disabled={busy || data.summary.status !== 'open'}
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Run Agent Decision
              </button>
              <button
                type="button"
                onClick={handleExecute}
                disabled={busy || !data.decision || data.decision.status !== 'auto_approved'}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Execute
              </button>
            </section>

            {/* Audit timeline */}
            <section>
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-4">Audit Timeline</p>
              <AuditTimeline events={data.events} />
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
