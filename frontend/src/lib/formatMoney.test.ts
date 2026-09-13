import { describe, expect, it } from 'vitest'

import { formatMoney } from './formatMoney'

describe('formatMoney', () => {
  it('renders cents as a currency amount', () => {
    expect(formatMoney(89900, 'USD')).toBe('$899.00')
  })

  it('keeps the record own currency rather than the locale default', () => {
    expect(formatMoney(89900, 'EUR')).toBe('€899.00')
  })

  it('renders zero', () => {
    expect(formatMoney(0, 'USD')).toBe('$0.00')
  })

  it('groups thousands', () => {
    expect(formatMoney(1234567, 'USD')).toBe('$12,345.67')
  })
})
