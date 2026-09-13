import type { Id, IsoDateTime, TenantScoped } from './common'

/** PRD §21. Placeholder data is acceptable for the MVP (USER_STORIES US-12.1). */
export type BillingStatus = 'active' | 'past_due' | 'trialing' | 'canceled'

export type InvoiceStatus = 'paid' | 'due' | 'overdue'

export interface UsageMetric {
  id: string
  label: string
  used: number
  included: number
  unit: string
}

export interface Invoice {
  id: Id
  number: string
  issuedAt: IsoDateTime
  amountCents: number
  currency: string
  status: InvoiceStatus
}

export interface BillingOverview extends TenantScoped {
  planName: string
  status: BillingStatus
  periodStart: IsoDateTime
  periodEnd: IsoDateTime
  /** Display-safe summary only, e.g. "Visa ending 4242" (PRD §47). */
  paymentMethod?: string
  usage: UsageMetric[]
  invoices: Invoice[]
}
