import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { organizationService } from './organizationService'

describe('organizationService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists organizations', async () => {
    const organizations = await organizationService.list()
    expect(organizations).toHaveLength(1)
    expect(organizations[0].name).toBe('Horizon Partners')
  })

  it('returns locations on the organization', async () => {
    const [organization] = await organizationService.list()
    expect(organization.locations.map((location) => location.name)).toEqual([
      'North Office',
      'Riverside Office',
    ])
  })

  it('returns the current organization', async () => {
    const current = await organizationService.getCurrent()
    expect(current.id).toBe('org_horizon')
  })
})
