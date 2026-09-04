import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { KpiCards } from './KpiCards'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

describe('KpiCards', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders every KPI with the values the API returned', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          revenue_at_risk_cents: 490000,
          recovered_revenue_cents: 125000,
          recovery_rate: 0.75,
          active_recovery_cases: 4,
          failed_payments: 12,
          human_escalations: 2,
        }),
      ),
    )
    render(<KpiCards />)
    await waitFor(() => expect(screen.getByText('₹4,900.00')).toBeInTheDocument())
    expect(screen.getByText('₹1,250.00')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    // The caption disambiguates recovery_rate (resolved / closed cases)
    // from the funnel's "Measure — Recovered" (recovered / all cases ever
    // opened) — without it, a 100% rate next to a lower funnel percentage
    // reads as a bug rather than two different, both-correct metrics.
    expect(screen.getByText('Of closed cases — 4 still active')).toBeInTheDocument()
  })

  it('renders an em dash and a "no cases closed yet" caption when there is no terminal case yet', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          revenue_at_risk_cents: 0,
          recovered_revenue_cents: 0,
          recovery_rate: null,
          active_recovery_cases: 0,
          failed_payments: 0,
          human_escalations: 0,
        }),
      ),
    )
    render(<KpiCards />)
    await waitFor(() => expect(screen.getByText('—')).toBeInTheDocument())
    expect(screen.getByText('No cases closed yet')).toBeInTheDocument()
  })

  it('omits the "still active" count once every case has reached a terminal state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          revenue_at_risk_cents: 0,
          recovered_revenue_cents: 11600,
          recovery_rate: 1.0,
          active_recovery_cases: 0,
          failed_payments: 14,
          human_escalations: 10,
        }),
      ),
    )
    render(<KpiCards />)
    await waitFor(() => expect(screen.getByText('100%')).toBeInTheDocument())
    expect(screen.getByText('Of closed cases')).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 500 })),
    )
    render(<KpiCards />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
