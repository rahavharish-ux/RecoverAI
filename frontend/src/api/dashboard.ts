import type {
  DashboardSummary,
  DecisionSummary,
  Economics,
  FailureCategory,
  FunnelStage,
  PriorityCase,
} from '../types/dashboard'

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`GET ${url} failed: ${response.status}`)
  return (await response.json()) as T
}

export const getDashboardSummary = () => getJson<DashboardSummary>('/api/v1/dashboard/summary')
export const getRecoveryFunnel = () => getJson<FunnelStage[]>('/api/v1/dashboard/funnel')
export const getFailureCategories = () => getJson<FailureCategory[]>('/api/v1/dashboard/failures')
export const getRecentDecisions = (limit = 20) => getJson<DecisionSummary[]>(`/api/v1/dashboard/decisions?limit=${limit}`)
export const getPriorityCases = (limit = 20) => getJson<PriorityCase[]>(`/api/v1/dashboard/priority-cases?limit=${limit}`)
export const getEconomics = () => getJson<Economics>('/api/v1/dashboard/economics')
