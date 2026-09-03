import type { Prediction } from '../types/prediction'

/** Reads the PREDICT stage's most recent read for a case. Returns null,
 * not an error, when no prediction exists yet (no model trained, or the
 * case has no diagnosed decline) — a case not having a prediction is a
 * normal, expected state, not a failure. */
export async function getCasePrediction(caseId: number): Promise<Prediction | null> {
  const response = await fetch(`/api/v1/cases/${caseId}/prediction`)
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(`Failed to load prediction for case ${caseId}: ${response.status}`)
  }
  return (await response.json()) as Prediction
}
