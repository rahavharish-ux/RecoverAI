import type { EvaluationSummary, ModelVersion } from '../types/ml'

async function getJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url)
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`GET ${url} failed: ${response.status}`)
  return (await response.json()) as T
}

export const getActiveModel = () => getJson<ModelVersion>('/api/v1/ml/model')
export const getActiveEvaluation = () => getJson<EvaluationSummary>('/api/v1/ml/evaluation')
