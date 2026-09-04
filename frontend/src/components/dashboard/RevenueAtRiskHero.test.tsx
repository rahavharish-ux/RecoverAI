import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RevenueAtRiskHero } from './RevenueAtRiskHero'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

describe('RevenueAtRiskHero', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders revenue at risk and recovered revenue from the real summary', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          revenue_at_risk_cents: 12450000,
          recovered_revenue_cents: 125000,
          recovery_rate: 0.5,
          active_recovery_cases: 4,
          failed_payments: 12,
          human_escalations: 2,
        }),
      ),
    )
    render(<RevenueAtRiskHero />)
    await waitFor(() => expect(screen.getByText('₹1,24,500.00')).toBeInTheDocument())
    expect(screen.getByText('₹1,250.00')).toBeInTheDocument()
    expect(screen.getByText((_, el) => el?.textContent === '4 cases currently active')).toBeInTheDocument()
  })

  it('uses the singular "case" when exactly one is active', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({
          revenue_at_risk_cents: 100,
          recovered_revenue_cents: 0,
          recovery_rate: null,
          active_recovery_cases: 1,
          failed_payments: 1,
          human_escalations: 0,
        }),
      ),
    )
    render(<RevenueAtRiskHero />)
    await waitFor(() =>
      expect(screen.getByText((_, el) => el?.textContent === '1 case currently active')).toBeInTheDocument(),
    )
  })

  it('shows an error state when the request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 500 })),
    )
    render(<RevenueAtRiskHero />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
