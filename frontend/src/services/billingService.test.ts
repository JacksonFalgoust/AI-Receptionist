import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { billingService } from './billingService'

describe('billingService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns the plan, status, and period', async () => {
    const overview = await billingService.getOverview()

    expect(overview.planName).toBe('Concierge Professional')
    expect(overview.status).toBe('active')
    expect(new Date(overview.periodEnd).getTime()).toBeGreaterThan(
      new Date(overview.periodStart).getTime(),
    )
  })

  it('returns the four usage metrics US-12.1 asks for', async () => {
    const overview = await billingService.getOverview()

    expect(overview.usage.map((metric) => metric.label)).toEqual([
      'Voice minutes',
      'Conversations',
      'SMS messages',
      'Workflow executions',
    ])
    expect(overview.usage.every((metric) => metric.used <= metric.included)).toBe(true)
  })

  it('summarises the payment method without exposing card details (PRD §47)', async () => {
    const overview = await billingService.getOverview()

    expect(overview.paymentMethod).toBe('Visa ending 4242')
    expect(overview.paymentMethod).not.toMatch(/\d{6,}/)
  })

  it('returns invoices newest first', async () => {
    const overview = await billingService.getOverview()
    const times = overview.invoices.map((invoice) => new Date(invoice.issuedAt).getTime())

    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })
})
