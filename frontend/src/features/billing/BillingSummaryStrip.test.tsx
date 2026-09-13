import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { BillingOverview } from '@/types'

import { BillingSummaryStrip } from './BillingSummaryStrip'

const BILLING: BillingOverview = {
  organizationId: 'org_horizon',
  planName: 'Concierge Professional',
  status: 'active',
  periodStart: '2026-08-30T00:00:00.000Z',
  periodEnd: '2026-09-29T00:00:00.000Z',
  paymentMethod: 'Visa ending 4242',
  usage: [],
  invoices: [],
}

describe('BillingSummaryStrip', () => {
  it('shows the plan, status, period, and payment method', () => {
    render(<BillingSummaryStrip billing={BILLING} />)

    expect(screen.getByText('Concierge Professional')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Aug 30 – Sep 29, 2026')).toBeInTheDocument()
    expect(screen.getByText('Visa ending 4242')).toBeInTheDocument()
  })

  it('states the absence of a payment method rather than leaving it blank', () => {
    render(<BillingSummaryStrip billing={{ ...BILLING, paymentMethod: undefined }} />)
    expect(screen.getByText('No payment method on file')).toBeInTheDocument()
  })

  it('renders a non-active subscription status', () => {
    render(<BillingSummaryStrip billing={{ ...BILLING, status: 'past_due' }} />)
    expect(screen.getByText('Past due')).toBeInTheDocument()
  })
})
