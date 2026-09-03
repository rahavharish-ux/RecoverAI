import type { Prediction } from '../types/prediction'

export interface IngestResult {
  payment_attempt: { id: number; attempt_number: number }
  case: { id: number; status: string; amount_at_risk_cents: number; currency: string }
  diagnosis: { decline_code: string; decline_class: string; explanation: string } | null
  prediction: Prediction | null
  policy_decision: {
    eligibilities: { action_type: string; allowed: boolean; reason_code: string; message: string }[]
  } | null
  deduplicated: boolean
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    const message = (detail as { detail?: { message?: string } | string } | null)?.detail
    const text = typeof message === 'string' ? message : message?.message
    throw new Error(text ?? `Request to ${url} failed: ${response.status}`)
  }
  return (await response.json()) as T
}

/** Every scenario in the Demo Center goes through this exact endpoint —
 * the same one a real gateway webhook would call. Nothing here is a
 * UI-only simulation; it's a real Detect event against the real backend. */
export function ingestPaymentAttempt(input: {
  invoiceId: number
  paymentMethodId: number
  amountCents: number
  declineCode: string
}): Promise<IngestResult> {
  return postJson<IngestResult>('/api/v1/payment-attempts', {
    invoice_id: input.invoiceId,
    payment_method_id: input.paymentMethodId,
    amount_cents: input.amountCents,
    decline_code: input.declineCode,
  })
}
