import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { integrationService } from './integrationService'

describe('integrationService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists integrations across every status', async () => {
    const integrations = await integrationService.list()
    expect(integrations.length).toBeGreaterThanOrEqual(10)
  })

  it('connects a not-connected integration', async () => {
    const connected = await integrationService.connect('int_reservations', {
      accountLabel: 'bookings@horizonpartners.example.com',
      credentials: { apiKey: 'super-secret-value' },
    })

    expect(connected.status).toBe('connected')
    expect(connected.connectedAccount).toBe('bookings@horizonpartners.example.com')
    expect(connected.lastActivityAt).toBeDefined()
  })

  it('never stores or returns the supplied credentials (PRD §17.3, §47)', async () => {
    const connected = await integrationService.connect('int_reservations', {
      accountLabel: 'bookings@horizonpartners.example.com',
      credentials: { apiKey: 'super-secret-value' },
    })

    expect(JSON.stringify(connected)).not.toContain('super-secret-value')
    expect(JSON.stringify(store.integrations)).not.toContain('super-secret-value')
  })

  it('repairs a connection error back to connected', async () => {
    const repaired = await integrationService.repair('int_scheduling', {
      accountLabel: 'scheduling@horizonpartners.example.com',
    })
    expect(repaired.status).toBe('connected')
  })

  it('repairs an expired authentication back to connected', async () => {
    const repaired = await integrationService.repair('int_customer_data', {
      accountLabel: 'data@horizonpartners.example.com',
    })
    expect(repaired.status).toBe('connected')
  })

  it('disconnects and clears the account label', async () => {
    const disconnected = await integrationService.disconnect('int_payments')

    expect(disconnected.status).toBe('not_connected')
    expect(disconnected.connectedAccount).toBeUndefined()
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(integrationService.disconnect('int_missing')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})
