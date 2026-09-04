import { describe, expect, it } from 'vitest'
import { formatMoney, formatPercent, friendlyDeclineReason, titleCase } from './format'

describe('formatMoney', () => {
  it('formats a small amount with two decimal places and the rupee symbol', () => {
    expect(formatMoney(2900)).toBe('₹29.00')
  })

  it('formats an amount with paise correctly', () => {
    expect(formatMoney(1842387)).toBe('₹18,423.87')
  })

  it('applies Indian digit grouping (lakhs) once the amount crosses ₹99,999 — the case the app never used to exercise', () => {
    expect(formatMoney(12450000)).toBe('₹1,24,500.00')
  })

  it('groups a crore-scale amount correctly', () => {
    expect(formatMoney(1050000000)).toBe('₹1,05,00,000.00')
  })

  it('formats zero', () => {
    expect(formatMoney(0)).toBe('₹0.00')
  })

  it('formats a negative amount (e.g. an action cost shown as a deduction)', () => {
    expect(formatMoney(-500)).toBe('-₹5.00')
  })
})

describe('formatPercent', () => {
  it('renders an em dash for null', () => {
    expect(formatPercent(null)).toBe('—')
  })

  it('renders a whole-number percentage by default', () => {
    expect(formatPercent(0.745)).toBe('75%')
  })

  it('respects a requested digit count', () => {
    expect(formatPercent(0.745, 1)).toBe('74.5%')
  })
})

describe('titleCase', () => {
  it('converts a snake_case code to title case', () => {
    expect(titleCase('processor_error')).toBe('Processor Error')
  })
})

describe('friendlyDeclineReason', () => {
  it('maps every known decline code to bank/PSP-style phrasing', () => {
    expect(friendlyDeclineReason('insufficient_funds')).toBe('Insufficient balance')
    expect(friendlyDeclineReason('card_declined')).toBe('Issuer declined')
    expect(friendlyDeclineReason('processor_error')).toBe('Bank server error')
    expect(friendlyDeclineReason('expired_card')).toBe('Card expired')
    expect(friendlyDeclineReason('invalid_method')).toBe('Payment method invalid')
    expect(friendlyDeclineReason('do_not_honor')).toBe('Declined by issuing bank')
    expect(friendlyDeclineReason('fraud_suspected')).toBe('Blocked — suspected fraud')
  })

  it('falls back to titleCase for anything unmapped, rather than throwing', () => {
    expect(friendlyDeclineReason('some_future_code')).toBe('Some Future Code')
  })
})
