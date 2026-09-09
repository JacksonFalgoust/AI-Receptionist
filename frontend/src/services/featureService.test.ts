import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { featureService } from './featureService'

describe('featureService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists every feature', async () => {
    const features = await featureService.list()
    expect(features.length).toBeGreaterThanOrEqual(9)
    expect(features.some((feature) => feature.highImpact)).toBe(true)
  })

  it('disables an enabled feature', async () => {
    const updated = await featureService.setEnabled('feat_sms', false)
    expect(updated.status).toBe('disabled')

    const features = await featureService.list()
    expect(features.find((feature) => feature.id === 'feat_sms')?.status).toBe('disabled')
  })

  it('enables a disabled feature', async () => {
    const updated = await featureService.setEnabled('feat_surveys', true)
    expect(updated.status).toBe('enabled')
  })

  it('refuses to enable a feature that still needs setup', async () => {
    await expect(featureService.setEnabled('feat_inventory', true)).rejects.toMatchObject({
      kind: 'validation',
    })
  })

  it('refuses to enable a feature whose integration is not connected', async () => {
    await expect(featureService.setEnabled('feat_order_status', true)).rejects.toMatchObject({
      kind: 'validation',
    })
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(featureService.setEnabled('feat_missing', true)).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})
