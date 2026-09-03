import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function installMockFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      if (url.includes('/dashboard/summary')) {
        return jsonResponse({
          revenue_at_risk_cents: 0,
          recovered_revenue_cents: 0,
          recovery_rate: null,
          active_recovery_cases: 0,
          failed_payments: 0,
          human_escalations: 0,
        })
      }
      if (url.includes('/dashboard/funnel')) return jsonResponse([])
      if (url.includes('/dashboard/failures')) return jsonResponse([])
      if (url.includes('/dashboard/decisions')) return jsonResponse([])
      if (url.includes('/dashboard/priority-cases')) return jsonResponse([])
      if (url.includes('/dashboard/economics')) {
        return jsonResponse({
          revenue_at_risk_cents: 0,
          potential_recoverable_cents: 0,
          recovered_revenue_cents: 0,
          recovery_attempts: 0,
          successful_recoveries: 0,
          human_escalations: 0,
          action_cost_cents: 0,
          net_recovery_value_cents: 0,
          note: 'Sandbox data.',
        })
      }
      return new Response(null, { status: 404 })
    }),
  )
}

describe('App', () => {
  beforeEach(() => {
    installMockFetch()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the dashboard as the default view', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Revenue Recovery Command Center' })).toBeInTheDocument()
  })

  it('renders every navigation item', () => {
    render(<App />)
    for (const label of ['Overview', 'Recovery Cases', 'Case Intelligence', 'Agent Activity', 'Model Intelligence']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    // Demo Center is rendered twice by design (desktop sidebar + mobile
    // utility row, toggled with responsive classes) — jsdom doesn't apply
    // CSS, so both are present in the tree even though only one is visible
    // at any given viewport in a real browser.
    expect(screen.getAllByRole('button', { name: 'Demo Center' }).length).toBeGreaterThanOrEqual(1)
  })

  it('navigates to the Demo Center', async () => {
    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Demo Center' })[0])
    expect(await screen.findByRole('heading', { name: 'Demo Center' })).toBeInTheDocument()
  })

  it('navigates to Case Intelligence and reports a not-found case gracefully', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Case Intelligence' }))
    await waitFor(() => expect(screen.getByText(/was not found/)).toBeInTheDocument())
  })

  it('navigates to Model Intelligence', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Model Intelligence' }))
    expect(await screen.findByRole('heading', { name: 'Model Intelligence' })).toBeInTheDocument()
  })

  it('navigates to Agent Activity', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Agent Activity' }))
    expect(await screen.findByRole('heading', { name: 'Agent Activity' })).toBeInTheDocument()
  })
})
