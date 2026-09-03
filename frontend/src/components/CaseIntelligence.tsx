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
import { CASE_STATUS_STYLES, CONFIDENCE_BAND_STYLES, RISK_FLAG_STYLES, riskFlagTone } from '../lib/theme'
import type { AgentDecision, CaseAction, CaseEvent, CaseSummary } from '../types/case'
import { AuditTimeline } from './AuditTimeline'
import { PipelineStepper } from './PipelineStepper'
import { Card } from './ui/Card'
import { ModeBadge } from './ui/ModeBadge'
import { ErrorState, LoadingState } from './ui/States'

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
  const requiresHumanReview = data?.decision?.status === 'human_review'
  const resolved = data?.summary.status === 'resolved'

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand">RecoverAI</p>
          <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink">Case Intelligence</h1>
        </div>
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            const parsed = Number.parseInt(caseIdInput, 10)
            if (Number.isFinite(parsed) && parsed > 0) setCaseId(parsed)
          }}
        >
          <label htmlFor="case-id" className="text-xs text-muted">
            Case #
          </label>
          <input
            id="case-id"
            value={caseIdInput}
            onChange={(e) => setCaseIdInput(e.target.value)}
            className="w-16 rounded border border-line-strong bg-surface px-2 py-1 text-sm tabular-nums text-ink focus:border-brand focus:outline-none"
          />
        </form>
      </header>

      {loading && <LoadingState label="Loading case…" />}
      {error && !loading && <ErrorState message={error} />}

      {data && !loading && (
        <div className="space-y-6">
          {/* Pipeline stepper — the whole story at a glance, hero surface */}
          <Card className="!bg-surface-2">
            <PipelineStepper
              events={data.events}
              busy={busy}
              requiresHumanReview={requiresHumanReview}
              resolved={resolved}
            />
          </Card>

          {/* Transaction */}
          <section>
            <p className="text-xs uppercase tracking-wide text-faint">Transaction</p>
            <p className="text-4xl font-bold tabular-nums text-ink">
              {formatMoney(data.summary.amount_at_risk_cents || data.summary.amount_recovered_cents)}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase ${CASE_STATUS_STYLES[data.summary.status]}`}>
                {data.summary.status}
              </span>
              {declineCode && <span className="text-xs text-muted">Failure: {titleCase(declineCode)}</span>}
            </div>
          </section>

          {/* Prediction */}
          {data.decision && data.decision.recovery_probability !== null && (
            <Card eyebrow="Predict" title="AI Recovery Prediction">
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-bold tabular-nums text-ink">{Math.round(data.decision.recovery_probability * 100)}%</span>
                <span className={`text-sm font-semibold uppercase ${CONFIDENCE_BAND_STYLES[confidenceBand(data.decision.recovery_probability)]}`}>
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
                        isSelected ? 'border-brand/40 bg-brand/10' : 'border-line bg-surface-2'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className={isSelected ? 'text-brand' : 'text-faint'}>{isSelected ? '✓' : '○'}</span>
                        <span className="text-ink">{titleCase(action.action_type)}</span>
                      </span>
                      <span className="tabular-nums text-muted">{formatMoney(action.expected_value_cents)}</span>
                    </li>
                  )
                })}
                {data.decision.available_actions.length === 0 && (
                  <li className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
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
                <p className="text-xs uppercase tracking-wide text-faint">Agent Decision</p>
                <ModeBadge agentMode={data.decision.agent_mode} label={data.decision.mode_label} />
              </div>
              <blockquote className="rounded-lg border-l-2 border-brand/50 bg-surface-2 px-4 py-3 text-sm italic text-muted">
                “{data.decision.reasoning_summary}”
              </blockquote>

              <div className="mt-4 border-t border-line pt-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-faint">Why this action?</p>
                <dl className="grid grid-cols-2 gap-y-3 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-faint">Recovery probability</dt>
                    <dd className="tabular-nums text-ink">{formatPercent(data.decision.recovery_probability)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-faint">Expected value</dt>
                    <dd className="tabular-nums text-ink">
                      {selectedActionValue !== null ? formatMoney(selectedActionValue) : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-faint">Action cost</dt>
                    <dd className="tabular-nums text-ink">
                      {selectedActionCost !== null ? formatMoney(selectedActionCost) : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-faint">Confidence</dt>
                    <dd className="tabular-nums text-ink">{Math.round(data.decision.confidence * 100)}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-faint">Policy eligibility</dt>
                    <dd className="text-ink">{data.decision.available_actions.length} action(s) allowed</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-faint">HITL status</dt>
                    <dd className={data.decision.requires_human_review ? 'text-danger' : 'text-success'}>
                      {data.decision.requires_human_review ? 'Review required' : 'Auto-approved'}
                    </dd>
                  </div>
                </dl>
                {data.decision.risk_flags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {data.decision.risk_flags.map((flag) => (
                      <span key={flag} className={`rounded-full border px-2 py-0.5 text-xs ${RISK_FLAG_STYLES[riskFlagTone(flag)]}`}>
                        {titleCase(flag)}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-3 text-xs text-faint">
                {data.decision.status !== 'human_review' && (
                  <span className="flex items-center gap-1 text-success">
                    <span>✓</span> Policy validation passed
                  </span>
                )}
                {data.decision.status === 'human_review' && (
                  <span className="flex items-center gap-1 text-danger">
                    <span>⚠</span> Human review required
                  </span>
                )}
              </div>
            </Card>
          )}

          {/* Action result */}
          {executedAction && (
            <Card
              className={resolved ? '!border-success/30 !bg-success/10' : ''}
              eyebrow="Measure"
              title="Action Result"
            >
              {resolved ? (
                <p className="text-sm text-success">
                  Recovery successful — {formatMoney(data.summary.amount_recovered_cents)} recovered.
                </p>
              ) : (
                <p className="text-sm text-muted">
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
              className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-40"
            >
              Run Agent Decision
            </button>
            <button
              type="button"
              onClick={handleExecute}
              disabled={busy || !data.decision || data.decision.status !== 'auto_approved'}
              className="rounded-md border border-line-strong px-4 py-2 text-sm font-medium text-ink transition-colors duration-150 hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
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
