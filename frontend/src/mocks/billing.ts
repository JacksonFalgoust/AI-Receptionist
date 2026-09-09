import type { BillingOverview } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const DAY = 24 * 60 * 60 * 1000

function isoDaysAgo(days: number): string {
  return new Date(NOW - days * DAY).toISOString()
}

/** PRD §21 / US-12.1: placeholder-grade data is acceptable, but never a card number (PRD §47). */
export const billingOverviewSeed: BillingOverview = {
  organizationId: MOCK_ORGANIZATION_ID,
  planName: 'Concierge Professional',
  status: 'active',
  periodStart: isoDaysAgo(12),
  periodEnd: isoDaysAgo(-18),
  paymentMethod: 'Visa ending 4242',
  usage: [
    { id: 'usage_voice', label: 'Voice minutes', used: 9600, included: 12000, unit: 'minutes' },
    { id: 'usage_conversations', label: 'Conversations', used: 1840, included: 3000, unit: 'conversations' },
    { id: 'usage_sms', label: 'SMS messages', used: 2410, included: 5000, unit: 'messages' },
    { id: 'usage_workflows', label: 'Workflow executions', used: 2692, included: 6000, unit: 'executions' },
  ],
  invoices: [
    { id: 'inv_0003', number: 'HP-2026-0003', issuedAt: isoDaysAgo(12), amountCents: 89900, currency: 'USD', status: 'due' },
    { id: 'inv_0002', number: 'HP-2026-0002', issuedAt: isoDaysAgo(42), amountCents: 89900, currency: 'USD', status: 'paid' },
    { id: 'inv_0001', number: 'HP-2026-0001', issuedAt: isoDaysAgo(72), amountCents: 89900, currency: 'USD', status: 'paid' },
  ],
}
