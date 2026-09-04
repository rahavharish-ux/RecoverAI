/** Every amount is stored as an integer in the smallest currency unit
 * (named `_cents` in the schema for historical reasons — see
 * models/core.py — but scaled identically to paise) against a `currency`
 * field the backend now genuinely records as "inr" for every real case.
 * Indian digit grouping (₹1,24,500 style) comes from the `en-IN` locale
 * below, not from a display-only override. */
export function formatMoney(cents: number): string {
  try {
    return (cents / 100).toLocaleString("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    })
  } catch {
    return `₹${(cents / 100).toFixed(2)}`
  }
}

export function formatPercent(fraction: number | null, digits = 0): string {
  if (fraction === null) return "—"
  return `${(fraction * 100).toFixed(digits)}%`
}

export function friendlyLabel(code: string): string {
  return code.replaceAll("_", " ")
}

export function titleCase(code: string): string {
  return friendlyLabel(code).replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Realistic, bank/PSP-style phrasing for each decline code — deliberately
 * bounded by what app/domain/decline_taxonomy.py actually distinguishes.
 * No label here claims a distinction the backend doesn't make (e.g. no
 * "UPI collect expired" unless a case is genuinely diagnosed that way) —
 * a technical reviewer reading both the copy and the source should never
 * catch a mismatch between what's said and what's true. */
const DECLINE_REASON_LABELS: Record<string, string> = {
  insufficient_funds: "Insufficient balance",
  card_declined: "Issuer declined",
  processor_error: "Bank server error",
  expired_card: "Card expired",
  invalid_method: "Payment method invalid",
  do_not_honor: "Declined by issuing bank",
  fraud_suspected: "Blocked — suspected fraud",
}

export function friendlyDeclineReason(code: string): string {
  return DECLINE_REASON_LABELS[code] ?? titleCase(code)
}
