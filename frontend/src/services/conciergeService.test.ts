import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { conciergeService } from './conciergeService'

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
})

describe('conciergeService configuration', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns the seeded configuration with nothing unpublished', async () => {
    const configuration = await conciergeService.getConfiguration()

    expect(configuration.businessProfile.name).toBe('Horizon Partners')
    expect(configuration.hasUnpublishedChanges).toBe(false)
  })

  it('saveDraft records the change without publishing it (PRD §13.4)', async () => {
    const before = await conciergeService.getConfiguration()

    const draft = await conciergeService.saveDraft({
      identity: { ...before.identity, greeting: 'Good morning, Horizon Partners.' },
    })

    expect(draft.identity.greeting).toBe('Good morning, Horizon Partners.')
    expect(draft.hasUnpublishedChanges).toBe(true)
    // Publishing markers must be untouched by a save.
    expect(draft.lastPublishedAt).toBe(before.lastPublishedAt)
    expect(store.conciergeStatus.lastConfigurationChangeAt).toBe(
      before.lastPublishedAt,
    )
  })

  it('saveDraft merges only the sections it is given', async () => {
    const before = await conciergeService.getConfiguration()

    const draft = await conciergeService.saveDraft({
      businessProfile: { ...before.businessProfile, phone: '+1 555 0199' },
    })

    expect(draft.businessProfile.phone).toBe('+1 555 0199')
    expect(draft.identity.greeting).toBe(before.identity.greeting)
    expect(draft.terminology).toEqual(before.terminology)
  })

  it('publish clears the flag and stamps both timestamps', async () => {
    const before = await conciergeService.getConfiguration()
    await conciergeService.saveDraft({
      identity: { ...before.identity, closing: 'Thanks for calling Horizon Partners.' },
    })

    const published = await conciergeService.publish()

    expect(published.hasUnpublishedChanges).toBe(false)
    expect(published.identity.closing).toBe('Thanks for calling Horizon Partners.')
    expect(new Date(published.lastPublishedAt!).getTime()).toBeGreaterThan(
      new Date(before.lastPublishedAt!).getTime(),
    )
    expect(store.conciergeStatus.lastConfigurationChangeAt).toBe(published.lastPublishedAt)
  })
})
