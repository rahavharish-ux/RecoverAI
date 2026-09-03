import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 404 })),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the Case Intelligence header', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Case Intelligence' })).toBeInTheDocument()
  })

  it('shows a not-found message when the case does not exist', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText(/was not found/)).toBeInTheDocument())
  })
})
