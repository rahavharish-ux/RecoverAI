export type CaseStatus = 'open' | 'escalated' | 'resolved'

export interface CaseSummary {
  id: number
  invoice_id: number
  customer_id: number
  status: CaseStatus
  amount_at_risk_cents: number
  amount_recovered_cents: number
  currency: string
  opened_at: string
  resolved_at: string | null
  resolution_reason: string | null
}

export interface CaseEvent {
  id: number
  case_id: number
  event_type: string
  actor: string
  summary: string
  details: Record<string, unknown>
  occurred_at: string
}

export interface AvailableAction {
  action_type: string
  reason_code: string
  message: string
  expected_value_cents: number
}

export type DecisionStatus = 'auto_approved' | 'human_review' | 'executed' | 'rejected' | 'escalated'

export interface AgentDecision {
  id: number
  case_id: number
  agent_mode: 'deterministic' | 'llm'
  provider_name: string
  mode_label: string
  policy_version: string
  available_actions: AvailableAction[]
  expected_values_cents: Record<string, number>
  recovery_probability: number | null
  selected_action: string | null
  reasoning_summary: string
  confidence: number
  risk_flags: string[]
  requires_human_review: boolean
  status: DecisionStatus
  executed_action_id: number | null
  reviewed_by: string | null
  reviewed_at: string | null
  review_note: string | null
  decided_at: string
}

export interface ActionOutcome {
  id: number
  action_id: number
  payment_attempt_id: number
  result: 'succeeded' | 'failed'
  amount_recovered_cents: number
  occurred_at: string
}

export interface CaseAction {
  id: number
  case_id: number
  action_type: string
  status: 'pending' | 'executed' | 'rejected'
  idempotency_key: string
  sequence: number
  requested_at: string
  executed_at: string | null
  rejection_reason: string | null
}
