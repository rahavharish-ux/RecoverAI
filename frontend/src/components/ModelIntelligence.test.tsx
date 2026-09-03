import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ModelIntelligence } from './ModelIntelligence'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const SAMPLE_MODEL = {
  id: 1,
  model_name: 'recovery_probability',
  algorithm: 'logistic_regression',
  version: 'v1756923725',
  dataset_version: 'synthetic-v1-seed42-cust1200',
  feature_schema_version: 'features-v1',
  is_calibrated: true,
  operating_threshold: 0.3,
  trained_at: '2026-09-03T18:22:05Z',
  is_active: true,
}

describe('ModelIntelligence', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders model metadata and the sandbox evaluation disclaimer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString()
        if (url.endsWith('/api/v1/ml/model')) return jsonResponse(SAMPLE_MODEL)
        if (url.endsWith('/api/v1/ml/evaluation')) {
          return jsonResponse({
            model_version: SAMPLE_MODEL,
            report: {
              split: { train_n: 3414, val_n: 732, test_n: 732, test_positive_rate: 0.25 },
              calibration: {
                'calibrated_test_metrics_at_0.5': { roc_auc: 0.862, pr_auc: 0.658, brier_score: 0.127, precision: 0.51, recall: 0.82, f1: 0.63 },
                brier_improved: true,
              },
            },
          })
        }
        if (url.includes('/dashboard/decisions')) return jsonResponse([])
        return new Response(null, { status: 404 })
      }),
    )

    render(<ModelIntelligence />)
    await waitFor(() => expect(screen.getByText('logistic_regression')).toBeInTheDocument())
    expect(screen.getByText('synthetic-v1-seed42-cust1200')).toBeInTheDocument()
    expect(screen.getByText(/Synthetic Sandbox Evaluation/i) ?? screen.getByText(/synthetic sandbox evaluation/i)).toBeTruthy()
    expect(screen.getByText('0.862')).toBeInTheDocument()
    expect(screen.getByText('0.127')).toBeInTheDocument()
    expect(screen.getByText(/no predictions yet/i)).toBeInTheDocument()
  })

  it('shows an empty state when no model has been trained', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 404 })),
    )
    render(<ModelIntelligence />)
    await waitFor(() => expect(screen.getByText(/no model trained yet/i)).toBeInTheDocument())
  })
})
