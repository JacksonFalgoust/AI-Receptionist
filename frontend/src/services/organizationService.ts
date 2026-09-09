import { store } from '@/mocks/store'
import type { Organization } from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

/**
 * PRD §41. One organization today — the header selector is real plumbing over
 * a list of length one, so Phase F's multi-organization switching swaps the
 * data rather than rewriting the control.
 */
export interface OrganizationService {
  list(): Promise<Organization[]>
  getCurrent(): Promise<Organization>
}

const mockOrganizationService: OrganizationService = {
  async list() {
    await delay()
    return [...store.organizations]
  },

  async getCurrent() {
    await delay()
    const [organization] = store.organizations
    if (!organization) {
      throw new AppError({
        kind: 'not_found',
        title: 'Organization not found',
        description: 'Your account is not linked to an organization. Contact support.',
      })
    }
    return organization
  },
}

const httpOrganizationService: OrganizationService = {
  list: () => http.get<Organization[]>('/organizations'),
  getCurrent: () => http.get<Organization>('/organizations/current'),
}

export const organizationService: OrganizationService = USE_MOCKS
  ? mockOrganizationService
  : httpOrganizationService
