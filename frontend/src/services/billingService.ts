import { store } from '@/mocks/store'
import type { BillingOverview } from '@/types'

import { delay, USE_MOCKS } from './config'
import { http } from './http'

/**
 * PRD §21 / US-12.1. Read-only for the MVP — plan changes and invoice
 * downloads are not in scope.
 */
export interface BillingService {
  getOverview(): Promise<BillingOverview>
}

const mockBillingService: BillingService = {
  async getOverview() {
    await delay()
    return store.billing
  },
}

const httpBillingService: BillingService = {
  getOverview: () => http.get<BillingOverview>('/billing/overview'),
}

export const billingService: BillingService = USE_MOCKS
  ? mockBillingService
  : httpBillingService
