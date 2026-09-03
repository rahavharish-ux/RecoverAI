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

describe('DemoCenter', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('runs a scenario through the real API sequence and shows the real outcome', async () => {
    const calls: { url: string; method: string }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        calls.push({ url, method: init?.method ?? 'GET' })

        if (url.endsWith('/api/v1/payment-attempts')) {
          return jsonResponse({
            payment_attempt: { id: 1, attempt_number: 1 },
            case: { id: 7, status: 'open', amount_at_risk_cents: 2900, currency: 'usd' },
            diagnosis: { decline_code: 'processor_error', decline_class: 'soft', explanation: 'A transient processor error.' },
            prediction: { recovery_probability: 0.7, confidence_band: 'high' },
            policy_decision: { eligibilities: [] },
            deduplicated: false,
          })
        }
        if (url.endsWith('/agent/decide')) {
          return jsonResponse(BASE_DECISION)
        }
        if (url.endsWith('/agent/execute')) {
          return jsonResponse({
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
            case: {
              id: 7,
              invoice_id: 1,
              customer_id: 1,
              status: 'resolved',
              amount_at_risk_cents: 0,
              amount_recovered_cents: 2900,
              currency: 'usd',
              opened_at: '2026-01-01T00:00:00Z',
              resolved_at: '2026-01-01T00:00:01Z',
              resolution_reason: 'payment_succeeded',
            },
            deduplicated: false,
          })
        }
        return new Response(null, { status: 404 })
      }),
    )

    const onOpenCase = vi.fn()
    render(<DemoCenter onOpenCase={onOpenCase} />)

    fireEvent.click(screen.getAllByRole('button', { name: 'Run Scenario' })[0])

    await waitFor(() => expect(screen.getByText('Payment Recovered')).toBeInTheDocument())
    expect(screen.getByText(/\$29\.00 recovered/)).toBeInTheDocument()
    expect(screen.getByText('Payment Failed')).toBeInTheDocument()
    expect(screen.getByText('Agent Decided')).toBeInTheDocument()

    // Every step is a real backend call, not scripted UI text.
    expect(calls.some((c) => c.url.endsWith('/api/v1/payment-attempts') && c.method === 'POST')).toBe(true)
    expect(calls.some((c) => c.url.endsWith('/agent/decide') && c.method === 'POST')).toBe(true)
    expect(calls.some((c) => c.url.endsWith('/agent/execute') && c.method === 'POST')).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'View Case Intelligence →' }))
    expect(onOpenCase).toHaveBeenCalledWith(7)
  })

  it('shows the human-review step and does not call execute when a decision requires review', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        if (url.endsWith('/api/v1/payment-attempts')) {
          return jsonResponse({
            payment_attempt: { id: 1, attempt_number: 1 },
            case: { id: 8, status: 'open', amount_at_risk_cents: 1900, currency: 'usd' },
            diagnosis: { decline_code: 'fraud_suspected', decline_class: 'fraud', explanation: 'Suspected fraud.' },
            prediction: { recovery_probability: 0.02, confidence_band: 'low' },
            policy_decision: { eligibilities: [] },
            deduplicated: false,
          })
        }
        if (url.endsWith('/agent/decide')) {
          return jsonResponse({ ...BASE_DECISION, case_id: 8, selected_action: 'escalate', status: 'human_review', requires_human_review: true, risk_flags: ['fraud_signal'] })
        }
        if (url.endsWith('/agent/execute')) {
          throw new Error('execute should not be called for a human_review decision')
        }
        void init
        return new Response(null, { status: 404 })
      }),
    )

    render(<DemoCenter onOpenCase={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Run Scenario' })[1])

    await waitFor(() => expect(screen.getByText('Human Review Required')).toBeInTheDocument())
  })
})
