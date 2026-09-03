/** Every amount in the system is stored as integer cents against a
 * currency field the backend happens to record as "usd" (a holdover from
 * the original synthetic dataset — see training/synthetic_data.py). This
 * is a display-only convention for the competition build: the same cent
 * value is rendered with the ₹ symbol and Indian digit grouping. No
 * backend data, amount, or business calculation changes. */
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
