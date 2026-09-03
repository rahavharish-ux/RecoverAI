import type { AgentDecision, CaseAction, CaseEvent, CaseSummary } from '../types/case'

async function getJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url)
  if (response.status === 404) return null
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

export const getCase = (caseId: number) => getJson<CaseSummary>(`/api/v1/cases/${caseId}`)
export const getCaseEvents = async (caseId: number) => (await getJson<CaseEvent[]>(`/api/v1/cases/${caseId}/events`)) ?? []
export const getCaseActions = async (caseId: number) => (await getJson<CaseAction[]>(`/api/v1/cases/${caseId}/actions`)) ?? []
export const getLatestDecision = (caseId: number) => getJson<AgentDecision>(`/api/v1/cases/${caseId}/decision`)

export const runAgentDecision = (caseId: number) => postJson<AgentDecision>(`/api/v1/cases/${caseId}/agent/decide`)

export interface ExecuteResult {
  agent_decision: AgentDecision
  case: CaseSummary
}

export const executeAgentDecision = (caseId: number) =>
  postJson<ExecuteResult>(`/api/v1/cases/${caseId}/agent/execute`, {})
