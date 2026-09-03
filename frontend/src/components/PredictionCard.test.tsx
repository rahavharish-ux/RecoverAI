import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PredictionCard } from './PredictionCard'
import type { Prediction } from '../types/prediction'

const SAMPLE_PREDICTION: Prediction = {
  id: 1,
  case_id: 42,
  payment_attempt_id: 101,
  recovery_probability: 0.62,
  confidence_band: 'medium',
  predicted_at: '2026-09-03T18:00:00Z',
  model_version: {
    id: 1,
    model_name: 'recovery_probability',
    algorithm: 'logistic_regression',
    version: 'v1756923725',
    dataset_version: 'synthetic-v1-seed42-cust1200',
    feature_schema_version: 'features-v1',
    is_calibrated: true,
    operating_threshold: 0.25,
    trained_at: '2026-09-03T18:22:05Z',
    is_active: true,
  },
  top_contributions: [
    {
      feature: 'customer_prior_recovery_rate',
      value: 0.8,
      direction: 'increases',
      weight: 0.42,
      is_exact_contribution: true,
    },
    { feature: 'retry_number', value: 1, direction: 'decreases', weight: 0.18, is_exact_contribution: true },
  ],
  expected_values_cents: { retry_payment: 2850, escalate: -500 },
  note: "recovery_probability is a sandbox model's estimate, trained and evaluated on synthetic data.",
}

describe('PredictionCard', () => {
  it('renders the probability as a percentage', () => {
    render(<PredictionCard prediction={SAMPLE_PREDICTION} />)
    expect(screen.getByText('62%')).toBeInTheDocument()
  })

  it('renders the confidence band', () => {
    render(<PredictionCard prediction={SAMPLE_PREDICTION} />)
    expect(screen.getByText(/medium confidence/i)).toBeInTheDocument()
  })

  it('renders each contributing feature', () => {
    render(<PredictionCard prediction={SAMPLE_PREDICTION} />)
    expect(screen.getByText(/customer prior recovery rate/)).toBeInTheDocument()
    expect(screen.getByText(/retry number/)).toBeInTheDocument()
  })

  it('renders the model version and algorithm', () => {
    render(<PredictionCard prediction={SAMPLE_PREDICTION} />)
    expect(screen.getByText(/logistic_regression/)).toBeInTheDocument()
  })

  it('renders nothing in the contribution list when there are no contributions', () => {
    render(<PredictionCard prediction={{ ...SAMPLE_PREDICTION, top_contributions: [] }} />)
    expect(screen.queryByText('Why')).not.toBeInTheDocument()
  })
})
