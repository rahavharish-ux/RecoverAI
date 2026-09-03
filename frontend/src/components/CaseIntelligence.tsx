import { useCallback, useEffect, useState } from 'react'
import {
  executeAgentDecision,
  getCase,
  getCaseActions,
  getCaseEvents,
  getLatestDecision,
  runAgentDecision,
} from '../api/cases'
import { getPolicyConfig, type PolicyConfig } from '../api/policy'
import { formatMoney, formatPercent, titleCase } from '../lib/format'
import type { AgentDecision, CaseAction, CaseEvent, CaseSummary } from '../types/case'
import { AuditTimeline } from './AuditTimeline'
import { PipelineStepper } from './PipelineStepper'
import { Card } from './ui/Card'
import { ModeBadge } from './ui/ModeBadge'
import { ErrorState, LoadingState } from './ui/States'

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

function confidenceBand(probability: number | null): 'low' | 'medium' | 'high' {
  if (probability === null) return 'low'
  if (probability >= 0.66) return 'high'
  if (probability >= 0.33) return 'medium'
  return 'low'
}

interface CaseData {
  summary: CaseSummary
  events: CaseEvent[]
  decision: AgentDecision | null
  actions: CaseAction[]
  policy: PolicyConfig | null
}

async function loadCase(caseId: number): Promise<CaseData | null> {
  const summary = await getCase(caseId)
  if (!summary) return null
  const [events, decision, actions, policy] = await Promise.all([
    getCaseEvents(caseId),
    getLatestDecision(caseId),
    getCaseActions(caseId),
    getPolicyConfig().catch(() => null),
  ])
  return { summary, events, decision, actions, policy }
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
  const selectedActionCost =
    data?.decision?.selected_action && data.policy
      ? (data.policy.action_costs_cents[data.decision.selected_action] ?? null)
      : null
  const selectedActionValue =
    data?.decision?.selected_action ? (data.decision.expected_values_cents[data.decision.selected_action] ?? null) : null

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
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

      {loading && <LoadingState label="Loading case…" />}
      {error && !loading && <ErrorState message={error} />}

      {data && !loading && (
        <div className="space-y-6">
          {/* Pipeline stepper — the whole story at a glance */}
          <Card>
            <PipelineStepper events={data.events} />
          </Card>

          {/* Transaction */}
          <section>
            <p className="text-xs uppercase tracking-wide text-slate-500">Transaction</p>
            <p className="text-4xl font-semibold tabular-nums">
              {formatMoney(data.summary.amount_at_risk_cents || data.summary.amount_recovered_cents, data.summary.currency)}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase ${STATUS_STYLES[data.summary.status]}`}>
                {data.summary.status}
              </span>
              {declineCode && <span className="text-xs text-slate-500">Failure: {titleCase(declineCode)}</span>}
            </div>
          </section>

          {/* Prediction */}
          {data.decision && data.decision.recovery_probability !== null && (
            <Card eyebrow="Predict" title="AI Recovery Prediction">
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-bold tabular-nums">{Math.round(data.decision.recovery_probability * 100)}%</span>
                <span className={`text-sm font-semibold uppercase ${BAND_STYLES[confidenceBand(data.decision.recovery_probability)]}`}>
                  {confidenceBand(data.decision.recovery_probability)} confidence
                </span>
              </div>
            </Card>
          )}

          {/* Available actions */}
          {data.decision && (
            <Card eyebrow="Decide" title="Available Actions">
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
                        <span className="capitalize">{titleCase(action.action_type)}</span>
                      </span>
                      <span className="tabular-nums text-slate-400">{formatMoney(action.expected_value_cents, data.summary.currency)}</span>
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
            </Card>
          )}

          {/* Agent decision + "Why this action?" */}
          {data.decision && (
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs uppercase tracking-wide text-slate-500">Agent Decision</p>
                <ModeBadge agentMode={data.decision.agent_mode} label={data.decision.mode_label} />
              </div>
              <blockquote className="rounded-lg border-l-2 border-violet-500/50 bg-slate-900 px-4 py-3 text-sm text-slate-300 italic">
                “{data.decision.reasoning_summary}”
              </blockquote>

              <div className="mt-4 border-t border-slate-800 pt-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Why this action?</p>
                <dl className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-slate-500">Recovery probability</dt>
                    <dd className="tabular-nums text-slate-200">{formatPercent(data.decision.recovery_probability)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Expected value</dt>
                    <dd className="tabular-nums text-slate-200">
                      {selectedActionValue !== null ? formatMoney(selectedActionValue, data.summary.currency) : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Action cost</dt>
                    <dd className="tabular-nums text-slate-200">
                      {selectedActionCost !== null ? formatMoney(selectedActionCost, data.summary.currency) : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Confidence</dt>
                    <dd className="tabular-nums text-slate-200">{Math.round(data.decision.confidence * 100)}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Policy eligibility</dt>
                    <dd className="text-slate-200">{data.decision.available_actions.length} action(s) allowed</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">HITL status</dt>
                    <dd className={data.decision.requires_human_review ? 'text-amber-400' : 'text-emerald-400'}>
                      {data.decision.requires_human_review ? 'Review required' : 'Auto-approved'}
                    </dd>
                  </div>
                </dl>
                {data.decision.risk_flags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {data.decision.risk_flags.map((flag) => (
                      <span key={flag} className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">
                        {titleCase(flag)}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-800 pt-3 text-xs text-slate-500">
                {data.decision.status !== 'human_review' && (
                  <span className="flex items-center gap-1 text-emerald-400">
                    <span>✓</span> Policy validation passed
                  </span>
                )}
                {data.decision.status === 'human_review' && (
                  <span className="flex items-center gap-1 text-amber-400">
                    <span>⚠</span> Human review required
                  </span>
                )}
              </div>
            </Card>
          )}

          {/* Action result */}
          {executedAction && (
            <Card
              className={
                data.summary.status === 'resolved'
                  ? '!border-emerald-500/30 !bg-emerald-500/10'
                  : ''
              }
              eyebrow="Measure"
              title="Action Result"
            >
              {data.summary.status === 'resolved' ? (
                <p className="text-sm text-emerald-300">
                  Recovery successful — {formatMoney(data.summary.amount_recovered_cents, data.summary.currency)} recovered.
                </p>
              ) : (
                <p className="text-sm text-slate-300">
                  {titleCase(executedAction.action_type)} executed — case remains {data.summary.status}.
                </p>
              )}
            </Card>
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
          <Card eyebrow="Audit" title="Audit Timeline">
            <AuditTimeline events={data.events} />
          </Card>
        </div>
      )}
    </div>
  )
}
