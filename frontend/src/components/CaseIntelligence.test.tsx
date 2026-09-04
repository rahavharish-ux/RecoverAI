import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CaseIntelligence } from './CaseIntelligence'
import type { AgentDecision, CaseEvent, CaseSummary } from '../types/case'
import type { PolicyConfig } from '../api/policy'

const SAMPLE_CASE: CaseSummary = {
  id: 1,
  invoice_id: 1,
  customer_id: 1,
  status: 'open',
  amount_at_risk_cents: 1249900,
  amount_recovered_cents: 0,
  currency: 'inr',
  opened_at: '2026-09-04T10:00:00Z',
  resolved_at: null,
  resolution_reason: null,
}

const SAMPLE_EVENTS: CaseEvent[] = [
  { id: 1, case_id: 1, event_type: 'case_opened', actor: 'system', summary: 'Case opened.', details: {}, occurred_at: '2026-09-04T10:00:00Z' },
  {
    id: 2,
    case_id: 1,
    event_type: 'diagnosed',
    actor: 'system',
    summary: 'Diagnosed as a soft decline (processor_error).',
    details: { decline_code: 'processor_error', decline_class: 'soft' },
    occurred_at: '2026-09-04T10:00:01Z',
  },
  { id: 3, case_id: 1, event_type: 'predicted', actor: 'system', summary: 'Estimated 78%.', details: {}, occurred_at: '2026-09-04T10:00:02Z' },
  { id: 4, case_id: 1, event_type: 'policy_evaluated', actor: 'system', summary: 'Policy allows retry.', details: {}, occurred_at: '2026-09-04T10:00:03Z' },
]

const SAMPLE_DECISION: AgentDecision = {
  id: 1,
  case_id: 1,
  agent_mode: 'deterministic',
  provider_name: 'deterministic-v1',
  mode_label: 'Deterministic Decision Engine',
  policy_version: 'policy-v1',
  available_actions: [
    { action_type: 'retry_payment', reason_code: 'eligible', message: 'ok', expected_value_cents: 974900 },
    { action_type: 'escalate', reason_code: 'eligible', message: 'ok', expected_value_cents: -50000 },
  ],
  expected_values_cents: { retry_payment: 974900, escalate: -50000 },
  recovery_probability: 0.78,
  selected_action: 'retry_payment',
  reasoning_summary:
    'The payment failure is classified as a transient processor error. Retry is currently policy-eligible and has the highest expected recovery value among allowed automated actions.',
  confidence: 0.78,
  risk_flags: [],
  requires_human_review: false,
  status: 'auto_approved',
  executed_action_id: null,
  reviewed_by: null,
  reviewed_at: null,
  review_note: null,
  decided_at: '2026-09-04T10:00:04Z',
}

const SAMPLE_POLICY: PolicyConfig = {
  policy_version: 'policy-v1',
  max_retry_attempts: 3,
  retry_cooldown_hours: 24,
  automated_actions_enabled: true,
  action_costs_cents: { retry_payment: 25, request_method_update: 10, escalate: 500 },
  note: 'illustrative sandbox configuration',
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function installMockFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.endsWith('/api/v1/cases/1/events')) return jsonResponse(SAMPLE_EVENTS)
      if (url.endsWith('/api/v1/cases/1/decision')) return jsonResponse(SAMPLE_DECISION)
      if (url.endsWith('/api/v1/cases/1/actions')) return jsonResponse([])
      if (url.endsWith('/api/v1/policy')) return jsonResponse(SAMPLE_POLICY)
      if (url.endsWith('/api/v1/cases/1')) return jsonResponse(SAMPLE_CASE)
      return new Response(null, { status: 404 })
    }),
  )
}

describe('CaseIntelligence', () => {
  beforeEach(() => {
    installMockFetch()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the transaction amount and status', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('₹12,499.00')).toBeInTheDocument())
    expect(screen.getByText('open')).toBeInTheDocument()
  })

  it('renders the failure reason from the diagnosis event', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('Failure: Processor Error')).toBeInTheDocument())
  })

  it('renders the recovery probability and confidence band', async () => {
    render(<CaseIntelligence />)
    // 78% legitimately appears twice: the hero prediction number and the
    // "Why this action?" panel's own probability field.
    await waitFor(() => expect(screen.getAllByText('78%').length).toBeGreaterThanOrEqual(2))
    expect(screen.getByText('high confidence')).toBeInTheDocument()
  })

  it('highlights the agent-selected action among the available ones', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('Retry Payment')).toBeInTheDocument())
    expect(screen.getByText('Escalate')).toBeInTheDocument()
  })

  it('renders the agent reasoning and mode label', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText(/transient processor error/)).toBeInTheDocument())
    expect(screen.getByText('Deterministic Decision Engine')).toBeInTheDocument()
  })

  it('shows policy validation passed for an auto-approved decision', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('Policy validation passed')).toBeInTheDocument())
  })

  it('renders the audit timeline in order', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('Diagnosed')).toBeInTheDocument())
    expect(screen.getByText('Predicted')).toBeInTheDocument()
    expect(screen.getByText('Policy Checked')).toBeInTheDocument()
  })

  it('renders the pipeline stepper with distinct stage labels', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('Diagnose')).toBeInTheDocument())
    // "Predict" and "Decide" each appear twice: once as a stepper stage
    // label, once as a Card eyebrow for the section covering that stage.
    expect(screen.getAllByText('Predict').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('Decide').length).toBeGreaterThanOrEqual(2)
    // "Audit" appears both as a stepper stage and as the timeline card's
    // title — both are real, expected occurrences of the same word.
    expect(screen.getAllByText('Audit').length).toBeGreaterThanOrEqual(2)
  })

  it('renders the "Why this action?" structured panel with expected value and cost', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByText('Why this action?')).toBeInTheDocument())
    // ₹9,749.00 (retry_payment's expected value) legitimately appears
    // twice: once in the Available Actions list, once in this panel.
    expect(screen.getAllByText('₹9,749.00').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('₹0.25')).toBeInTheDocument() // action cost for retry_payment
    expect(screen.getByText('Auto-approved')).toBeInTheDocument()
  })

  it('disables Execute until a decision is auto-approved and enabled here', async () => {
    render(<CaseIntelligence />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Execute' })).toBeEnabled())
  })
})
