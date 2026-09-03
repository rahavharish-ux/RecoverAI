export type ConfidenceBand = 'low' | 'medium' | 'high'

export interface FeatureContribution {
  feature: string
  value: number | string
  direction: 'increases' | 'decreases' | 'n/a'
  weight: number
  is_exact_contribution: boolean
}

export interface ModelVersionSummary {
  id: number
  model_name: string
  algorithm: string
  version: string
  dataset_version: string
  feature_schema_version: string
  is_calibrated: boolean
  operating_threshold: number
  trained_at: string
  is_active: boolean
}

export interface Prediction {
  id: number
  case_id: number
  payment_attempt_id: number
  recovery_probability: number
  confidence_band: ConfidenceBand
  predicted_at: string
  model_version: ModelVersionSummary
  top_contributions: FeatureContribution[]
  expected_values_cents: Record<string, number>
  note: string
}
