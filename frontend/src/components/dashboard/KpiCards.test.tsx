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
  })

  it('renders an em dash for recovery rate when there is no terminal case yet', async () => {
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
