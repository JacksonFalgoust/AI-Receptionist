import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { routingService } from './routingService'

describe('routingService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists rules by priority, lowest number first', async () => {
    const rules = await routingService.list()
    const priorities = rules.map((rule) => rule.priority)

    expect(rules.length).toBeGreaterThanOrEqual(8)
    expect([...priorities].sort((a, b) => a - b)).toEqual(priorities)
  })

  it('creates a rule at the end of the priority order', async () => {
    const created = await routingService.create({
      name: 'VIP clients go straight to advisory',
      condition: 'vip_customer',
      destination: { type: 'department', value: 'Advisory' },
      schedule: 'always',
      priority: 9,
      enabled: true,
    })

    expect(created.id).toBeDefined()
    expect((await routingService.list()).some((rule) => rule.id === created.id)).toBe(true)
  })

  it('updates a rule', async () => {
    const updated = await routingService.update('rr_0003', {
      destination: { type: 'team', value: 'Client care' },
    })

    expect(updated.destination).toEqual({ type: 'team', value: 'Client care' })
  })

  it('toggles a rule inline', async () => {
    expect((await routingService.setEnabled('rr_0007', true)).enabled).toBe(true)
    expect((await routingService.setEnabled('rr_0001', false)).enabled).toBe(false)
  })

  it('removes a rule', async () => {
    await routingService.remove('rr_0008')
    expect((await routingService.list()).some((rule) => rule.id === 'rr_0008')).toBe(false)
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(routingService.remove('rr_9999')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})
