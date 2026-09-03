export function formatMoney(cents: number, currency = 'usd'): string {
  try {
    return (cents / 100).toLocaleString(undefined, { style: 'currency', currency: currency.toUpperCase() })
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`
  }
}

export function formatPercent(fraction: number | null, digits = 0): string {
  if (fraction === null) return '—'
  return `${(fraction * 100).toFixed(digits)}%`
}

export function friendlyLabel(code: string): string {
  return code.replaceAll('_', ' ')
}

export function titleCase(code: string): string {
  return friendlyLabel(code).replace(/\b\w/g, (c) => c.toUpperCase())
}
