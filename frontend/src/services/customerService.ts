import { buildCustomerDetail, buildCustomerFixtures } from '@/mocks/customers'
import { matchesSearch, paginate } from '@/mocks/query'
import type { CustomerDetail, CustomerListParams, CustomersPage } from '@/types'

import { delay, isLive } from './config'
import { AppError, isAppError } from './errors'
import { http } from './http'
import { toQueryString } from './queryString'

/** Read-only customers, read live from Booqable by the backend. */
export interface CustomerService {
  list(params?: CustomerListParams): Promise<CustomersPage>
  get(id: string): Promise<CustomerDetail>
}

const mockCustomerService: CustomerService = {
  async list(params = {}) {
    await delay()
    const { q, page, pageSize } = params
    const matching = buildCustomerFixtures()
      .filter((c) => matchesSearch([c.name ?? undefined, c.email ?? undefined, c.phone ?? undefined], q))
      .sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''))
    return { ...paginate(matching, { page, pageSize }), fetchedAt: new Date().toISOString() }
  },
  async get(id) {
    await delay()
    const detail = buildCustomerDetail(id)
    if (!detail) throw notFound()
    return { ...detail, fetchedAt: new Date().toISOString() }
  },
}

function notFound(): AppError {
  return new AppError({
    kind: 'not_found',
    title: 'Customer not found',
    description: 'This customer may have been removed from Booqable.',
    actions: [{ label: 'Back to customers', href: '/customers' }],
  })
}

export const httpCustomerService: CustomerService = {
  async list(params = {}) {
    try {
      return await http.get<CustomersPage>(`/customers${toQueryString({ ...params })}`)
    } catch (error) {
      throw unreachable(error)
    }
  },
  async get(id) {
    try {
      return await http.get<CustomerDetail>(`/customers/${encodeURIComponent(id)}`)
    } catch (error) {
      if (isAppError(error) && error.kind === 'not_found') throw notFound()
      throw unreachable(error)
    }
  },
}

function unreachable(error: unknown): unknown {
  // Session expiry must still reach the auth handling.
  if (isAppError(error) && error.kind === 'unauthorized') return error
  return new AppError({
    kind: 'server',
    title: "Couldn't reach Booqable",
    description: 'Customers are read live from Booqable. Try again in a moment.',
    actions: [{ label: 'Try again', retry: true }],
  })
}

export const customerService: CustomerService = isLive('customers')
  ? httpCustomerService
  : mockCustomerService
