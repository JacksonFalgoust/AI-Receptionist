import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { conciergeService } from './conciergeService'
import { configurationService } from './configurationService'

describe('conciergeService status', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns the state, channels, and connected systems', async () => {
    const status = await conciergeService.getStatus()

    expect(status.state).toBe('active')
    expect(status.channels.map((channel) => channel.channel)).toEqual(['voice', 'sms'])
    expect(status.connectedSystems.length).toBeGreaterThan(0)
  })

  it('pauses and resumes', async () => {
    expect((await conciergeService.pause()).state).toBe('paused')
    expect((await conciergeService.getStatus()).state).toBe('paused')

    expect((await conciergeService.resume()).state).toBe('active')
    expect((await conciergeService.getStatus()).state).toBe('active')
  })

  it('hands back a new status object on every write, so cached readers re-render', async () => {
    const before = await conciergeService.getStatus()

    expect(await conciergeService.pause()).not.toBe(before)
    expect(await conciergeService.resume()).not.toBe(before)

    // Publishing stamps the status card's "last configuration change" line.
    const beforePublish = await conciergeService.getStatus()
    await configurationService.publish()
    const afterPublish = await conciergeService.getStatus()

    expect(afterPublish).not.toBe(beforePublish)
    expect(afterPublish.lastConfigurationChangeAt).not.toBe(
      beforePublish.lastConfigurationChangeAt,
    )
  })
})
