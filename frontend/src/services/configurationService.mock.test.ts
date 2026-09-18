import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { configurationService } from './configurationService'

/**
 * Exercises the mock implementation directly (no env stubbing, no `./http`
 * mock) — this is what every other consumer actually runs against in tests
 * and local dev until `configuration` is added to `VITE_LIVE_SERVICES` in a
 * real environment. `configurationService.test.ts` covers the http
 * implementation separately, with `isLive('configuration')` forced on.
 */
describe('configurationService (mock)', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns the seeded configuration with nothing unpublished', async () => {
    const configuration = await configurationService.getConfiguration()

    expect(configuration.businessProfile.name).toBe('Horizon Partners')
    expect(configuration.hasUnpublishedChanges).toBe(false)
  })

  it('saveDraft records the change without publishing it (PRD §13.4)', async () => {
    const before = await configurationService.getConfiguration()

    const draft = await configurationService.saveDraft({
      identity: { ...before.identity, greeting: 'Good morning, Horizon Partners.' },
    })

    expect(draft.identity.greeting).toBe('Good morning, Horizon Partners.')
    expect(draft.hasUnpublishedChanges).toBe(true)
    // Publishing markers must be untouched by a save.
    expect(draft.lastPublishedAt).toBe(before.lastPublishedAt)
    expect(store.conciergeStatus.lastConfigurationChangeAt).toBe(before.lastPublishedAt)
  })

  it('saveDraft merges only the sections it is given', async () => {
    const before = await configurationService.getConfiguration()

    const draft = await configurationService.saveDraft({
      businessProfile: { ...before.businessProfile, phone: '+1 555 0199' },
    })

    expect(draft.businessProfile.phone).toBe('+1 555 0199')
    expect(draft.identity.greeting).toBe(before.identity.greeting)
    expect(draft.terminology).toEqual(before.terminology)
  })

  it('publish clears the flag, stamps both timestamps, and reports success', async () => {
    const before = await configurationService.getConfiguration()
    await configurationService.saveDraft({
      identity: { ...before.identity, closing: 'Thanks for calling Horizon Partners.' },
    })

    const result = await configurationService.publish()

    expect(result.published).toBe(true)
    expect(result.configuration.hasUnpublishedChanges).toBe(false)
    expect(result.configuration.identity.closing).toBe('Thanks for calling Horizon Partners.')
    expect(new Date(result.configuration.lastPublishedAt!).getTime()).toBeGreaterThan(
      new Date(before.lastPublishedAt!).getTime(),
    )
    expect(store.conciergeStatus.lastConfigurationChangeAt).toBe(
      result.configuration.lastPublishedAt,
    )
  })

  it('preview reflects whether there are unpublished changes', async () => {
    const before = await configurationService.getConfiguration()
    expect((await configurationService.preview()).changed).toBe(before.hasUnpublishedChanges)

    await configurationService.saveDraft({
      identity: { ...before.identity, greeting: 'A brand new greeting.' },
    })

    expect((await configurationService.preview()).changed).toBe(true)
  })

  it('listPublications and rollback resolve without throwing', async () => {
    expect(await configurationService.listPublications()).toEqual([])

    const result = await configurationService.rollback('some-publication-id')
    expect(result.published).toBe(true)
  })
})
