import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DemoCenter } from './DemoCenter'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const BASE_DECISION = {
  id: 1,
  case_id: 7,
  agent_mode: 'deterministic',
  provider_name: 'deterministic-v1',
  mode_label: 'Deterministic Decision Engine',
  policy_version: 'policy-v1',
  available_actions: [{ action_type: 'retry_payment', reason_code: 'eligible', message: 'ok', expected_value_cents: 2500 }],
  expected_values_cents: { retry_payment: 2500 },
  recovery_probability: 0.7,
  selected_action: 'retry_payment',
  reasoning_summary: 'Transient processor error, retry is policy-eligible with the highest expected value.',
  confidence: 0.7,
  risk_flags: [],
  requires_human_review: false,
  status: 'auto_approved',
  executed_action_id: null,
  reviewed_by: null,
  reviewed_at: null,
  review_note: null,
  decided_at: '2026-01-01T00:00:00Z',
}

const BASE_CASE = {
  id: 7,
  invoice_id: 101,
  customer_id: 55,
  amount_at_risk_cents: 2900,
  amount_recovered_cents: 0,
  currency: 'inr',
  opened_at: '2026-01-01T00:00:00Z',
  resolved_at: null,
  resolution_reason: null,
}

function stubScenarioRun(body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (/\/api\/v1\/demo\/scenarios\/[A-Z]\/run$/.test(url)) {
        void init
        return jsonResponse(body)
      }
      return new Response(null, { status: 404 })
    }),
  )
}

describe('DemoCenter', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('runs a scenario through a single real backend call and shows the real recovered outcome', async () => {
    const calls: { url: string; method: string }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        calls.push({ url, method: init?.method ?? 'GET' })
        if (/\/api\/v1\/demo\/scenarios\/A\/run$/.test(url)) {
          return jsonResponse({
            scenario_id: 'A',
            ingest: {
              payment_attempt: { id: 1, attempt_number: 1 },
              case: { ...BASE_CASE, status: 'open' },
              diagnosis: { decline_code: 'processor_error', decline_class: 'soft', explanation: 'A transient processor error.' },
              prediction: { recovery_probability: 0.7, confidence_band: 'high' },
              deduplicated: false,
            },
            decision: BASE_DECISION,
            execute: {
              agent_decision: { ...BASE_DECISION, status: 'executed' },
              action: {
                id: 1,
                case_id: 7,
                action_type: 'retry_payment',
                status: 'executed',
                idempotency_key: 'x',
                sequence: 1,
                requested_at: '2026-01-01T00:00:00Z',
                executed_at: '2026-01-01T00:00:01Z',
                rejection_reason: null,
              },
              outcome: { id: 1, action_id: 1, payment_attempt_id: 2, result: 'succeeded', amount_recovered_cents: 2900, occurred_at: '2026-01-01T00:00:01Z' },
              case: { ...BASE_CASE, status: 'resolved', amount_at_risk_cents: 0, amount_recovered_cents: 2900, resolution_reason: 'payment_succeeded' },
              deduplicated: false,
            },
            second_decision: null,
            demo_fixture_applied: true,
          })
        }
        return new Response(null, { status: 404 })
      }),
    )

    const onOpenCase = vi.fn()
    render(<DemoCenter onOpenCase={onOpenCase} />)

    fireEvent.click(screen.getAllByRole('button', { name: 'Run Scenario' })[0])

    await waitFor(() => expect(screen.getByText('Payment Recovered')).toBeInTheDocument())
    expect(screen.getByText(/₹29\.00 recovered/)).toBeInTheDocument()
    expect(screen.getByText('Payment Failed')).toBeInTheDocument()
    expect(screen.getByText('Agent Decided')).toBeInTheDocument()

    // A single real backend call runs the whole pipeline — no separate
    // client-side ingest/decide/execute calls, and no hardcoded UI text.
    expect(calls.some((c) => /\/api\/v1\/demo\/scenarios\/A\/run$/.test(c.url) && c.method === 'POST')).toBe(true)
    expect(calls).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'View Case Intelligence →' }))
    expect(onOpenCase).toHaveBeenCalledWith(7)
  })

  it('shows a genuine failed-retry outcome when the backend reports one — no fabricated success state', async () => {
    stubScenarioRun({
      scenario_id: 'A',
      ingest: {
        payment_attempt: { id: 1, attempt_number: 1 },
        case: { ...BASE_CASE, status: 'open' },
        diagnosis: { decline_code: 'processor_error', decline_class: 'soft', explanation: 'A transient processor error.' },
        prediction: { recovery_probability: 0.7, confidence_band: 'high' },
        deduplicated: false,
      },
      decision: BASE_DECISION,
      execute: {
        agent_decision: { ...BASE_DECISION, status: 'executed' },
        action: {
          id: 1,
          case_id: 7,
          action_type: 'retry_payment',
          status: 'executed',
          idempotency_key: 'x',
          sequence: 1,
          requested_at: '2026-01-01T00:00:00Z',
          executed_at: '2026-01-01T00:00:01Z',
          rejection_reason: null,
        },
        outcome: { id: 1, action_id: 1, payment_attempt_id: 2, result: 'failed', amount_recovered_cents: 0, occurred_at: '2026-01-01T00:00:01Z' },
        case: { ...BASE_CASE, status: 'open' },
        deduplicated: false,
      },
      second_decision: null,
      demo_fixture_applied: false,
    })

    render(<DemoCenter onOpenCase={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Run Scenario' })[0])

    await waitFor(() => expect(screen.getByText('Retry Failed')).toBeInTheDocument())
    expect(screen.queryByText('Payment Recovered')).not.toBeInTheDocument()
    expect(screen.queryByText(/recovered\./)).not.toBeInTheDocument()
  })

  it('shows the human-review step and renders no execution step when a decision requires review', async () => {
    stubScenarioRun({
      scenario_id: 'B',
      ingest: {
        payment_attempt: { id: 1, attempt_number: 1 },
        case: { ...BASE_CASE, id: 8, status: 'open', amount_at_risk_cents: 1900 },
        diagnosis: { decline_code: 'fraud_suspected', decline_class: 'fraud', explanation: 'Suspected fraud.' },
        prediction: { recovery_probability: 0.02, confidence_band: 'low' },
        deduplicated: false,
      },
      decision: {
        ...BASE_DECISION,
        case_id: 8,
        selected_action: 'escalate',
        status: 'human_review',
        requires_human_review: true,
        risk_flags: ['fraud_signal'],
      },
      execute: null,
      second_decision: null,
      demo_fixture_applied: false,
    })

    render(<DemoCenter onOpenCase={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Run Scenario' })[1])

    await waitFor(() => expect(screen.getByText('Human Review Required')).toBeInTheDocument())
    expect(screen.queryByText('Payment Recovered')).not.toBeInTheDocument()
    expect(screen.queryByText('Action Executed')).not.toBeInTheDocument()
  })

  it('renders the second-decision cooldown-protection step when the backend reports one', async () => {
    stubScenarioRun({
      scenario_id: 'D',
      ingest: {
        payment_attempt: { id: 1, attempt_number: 1 },
        case: { ...BASE_CASE, status: 'open' },
        diagnosis: { decline_code: 'insufficient_funds', decline_class: 'soft', explanation: 'Insufficient funds.' },
        prediction: { recovery_probability: 0.55, confidence_band: 'medium' },
        deduplicated: false,
      },
      decision: BASE_DECISION,
      execute: {
        agent_decision: { ...BASE_DECISION, status: 'executed' },
        action: {
          id: 1,
          case_id: 7,
          action_type: 'retry_payment',
          status: 'executed',
          idempotency_key: 'x',
          sequence: 1,
          requested_at: '2026-01-01T00:00:00Z',
          executed_at: '2026-01-01T00:00:01Z',
          rejection_reason: null,
        },
        outcome: { id: 1, action_id: 1, payment_attempt_id: 2, result: 'failed', amount_recovered_cents: 0, occurred_at: '2026-01-01T00:00:01Z' },
        case: { ...BASE_CASE, status: 'open' },
        deduplicated: false,
      },
      second_decision: {
        ...BASE_DECISION,
        id: 2,
        reasoning_summary: 'Retry is on cooldown — no safe automated action remains.',
        available_actions: [],
        selected_action: null,
      },
      demo_fixture_applied: false,
    })

    render(<DemoCenter onOpenCase={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Run Scenario' })[3])

    await waitFor(() => expect(screen.getByText('Second Decision — Protection Check')).toBeInTheDocument())
  })
})
