import type { AgentDecision, CaseAction, CaseSummary, ActionOutcome as CaseActionOutcome } from '../types/case'
import type { Prediction } from '../types/prediction'

export interface DemoScenarioExecuteResult {
  agent_decision: AgentDecision
  action: CaseAction | null
  outcome: CaseActionOutcome | null
  case: CaseSummary
  deduplicated: boolean
}

/** The full, real result of one Demo Center scenario run — every field
 * traces back to a persisted database row (see backend
 * app/services/demo_service.py). Nothing here is assembled client-side:
 * the frontend only formats what the backend already computed. */
export interface DemoScenarioRunResult {
  scenario_id: string
  ingest: {
    payment_attempt: { id: number; attempt_number: number }
    case: CaseSummary
    diagnosis: { decline_code: string; decline_class: string; explanation: string } | null
    prediction: Prediction | null
    deduplicated: boolean
  }
  decision: AgentDecision
  execute: DemoScenarioExecuteResult | null
  second_decision: AgentDecision | null
  demo_fixture_applied: boolean
}

async function postJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    const message = (detail as { detail?: { message?: string } | string } | null)?.detail
    const text = typeof message === 'string' ? message : message?.message
    throw new Error(text ?? `Request to ${url} failed: ${response.status}`)
  }
  return (await response.json()) as T
}

/** Runs one Demo Center scenario end to end against a freshly created,
 * fully isolated synthetic transaction — the real DETECT -> DIAGNOSE ->
 * PREDICT -> DECIDE -> ACT -> MEASURE -> AUDIT pipeline, server-side, in a
 * single call. Every run gets its own case; nothing is reused across
 * runs, and nothing here is a UI-only simulation. */
export function runDemoScenario(scenarioId: string): Promise<DemoScenarioRunResult> {
  return postJson<DemoScenarioRunResult>(`/api/v1/demo/scenarios/${scenarioId}/run`)
}
