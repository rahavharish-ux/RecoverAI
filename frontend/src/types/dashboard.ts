export interface DashboardSummary {
  revenue_at_risk_cents: number
  recovered_revenue_cents: number
  recovery_rate: number | null
  active_recovery_cases: number
  failed_payments: number
  human_escalations: number
}

export interface FunnelStage {
  stage: string
  case_count: number
  pct_of_failed: number
}

export interface FailureCategory {
  decline_code: string
  decline_class: string
  retry_eligible: boolean
  case_count: number
  amount_involved_cents: number
  resolved_count: number
  escalated_count: number
  open_count: number
}

export interface DecisionSummary {
  decision_id: number
  case_id: number
  amount_at_risk_cents: number
  decline_code: string | null
  recovery_probability: number | null
  selected_action: string | null
  expected_value_cents: number | null
  agent_mode: 'deterministic' | 'llm'
  mode_label: string
  risk_flags: string[]
  status: string
  decided_at: string
}

export interface PriorityCase {
  case_id: number
  amount_at_risk_cents: number
  decline_code: string | null
  recovery_probability: number | null
  expected_value_cents: number | null
  risk_level: 'low' | 'medium' | 'high'
  recommended_action: string | null
  requires_human_review: boolean
}

export interface Economics {
  revenue_at_risk_cents: number
  potential_recoverable_cents: number
  recovered_revenue_cents: number
  recovery_attempts: number
  successful_recoveries: number
  human_escalations: number
  action_cost_cents: number
  net_recovery_value_cents: number
  note: string
}
