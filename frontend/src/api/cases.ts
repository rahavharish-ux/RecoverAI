import type { AgentDecision, CaseAction, CaseEvent, CaseSummary } from '../types/case'

async function getJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url)
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`GET ${url} failed: ${response.status}`)
  return (await response.json()) as T
}

async function getJsonRequired<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`GET ${url} failed: ${response.status}`)
  return (await response.json()) as T
}

async function postJson<T>(url: string, body: unknown = {}): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error((detail as { detail?: { message?: string } }).detail?.message ?? `POST ${url} failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export const listCases = (status?: string) =>
  getJsonRequired<CaseSummary[]>(`/api/v1/cases${status ? `?status=${status}` : ''}`)
export const getCase = (caseId: number) => getJson<CaseSummary>(`/api/v1/cases/${caseId}`)
export const getCaseEvents = async (caseId: number) => (await getJson<CaseEvent[]>(`/api/v1/cases/${caseId}/events`)) ?? []
export const getCaseActions = async (caseId: number) => (await getJson<CaseAction[]>(`/api/v1/cases/${caseId}/actions`)) ?? []
export const getLatestDecision = (caseId: number) => getJson<AgentDecision>(`/api/v1/cases/${caseId}/decision`)

export const runAgentDecision = (caseId: number) => postJson<AgentDecision>(`/api/v1/cases/${caseId}/agent/decide`)

export interface ActionOutcomeResult {
  id: number
  action_id: number
  payment_attempt_id: number
  result: 'succeeded' | 'failed'
  amount_recovered_cents: number
  occurred_at: string
}

export interface ExecuteResult {
  agent_decision: AgentDecision
  action: CaseAction | null
  outcome: ActionOutcomeResult | null
  case: CaseSummary
  deduplicated: boolean
}

export const executeAgentDecision = (caseId: number) =>
  postJson<ExecuteResult>(`/api/v1/cases/${caseId}/agent/execute`, {})
