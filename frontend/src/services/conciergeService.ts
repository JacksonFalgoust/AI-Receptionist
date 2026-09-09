import { store } from '@/mocks/store'
import type { ConciergeConfiguration, ConciergeStatus } from '@/types'

import { delay, USE_MOCKS } from './config'
import { http } from './http'

/** Only the sections a user edits. Tenancy and publishing markers are not patchable. */
export type ConciergeConfigurationPatch = Partial<
  Pick<ConciergeConfiguration, 'businessProfile' | 'identity' | 'terminology'>
>

/** PRD §6.2 (status) and §13 (configuration). */
export interface ConciergeService {
  getStatus(): Promise<ConciergeStatus>
  pause(): Promise<ConciergeStatus>
  resume(): Promise<ConciergeStatus>
  getConfiguration(): Promise<ConciergeConfiguration>
  /**
   * PRD §13.4: records an edit as a draft. Never reaches production customers —
   * only `publish()` does that.
   */
  saveDraft(patch: ConciergeConfigurationPatch): Promise<ConciergeConfiguration>
  publish(): Promise<ConciergeConfiguration>
}

const mockConciergeService: ConciergeService = {
  async getStatus() {
    await delay()
    return store.conciergeStatus
  },

  async pause() {
    await delay(120)
    store.conciergeStatus.state = 'paused'
    return store.conciergeStatus
  },

  async resume() {
    await delay(120)
    store.conciergeStatus.state = 'active'
    return store.conciergeStatus
  },

  async getConfiguration() {
    await delay()
    return store.conciergeConfiguration
  },

  async saveDraft(patch) {
    await delay()
    // Section-level merge: passing `identity` alone must not wipe the profile.
    store.conciergeConfiguration = {
      ...store.conciergeConfiguration,
      ...patch,
      hasUnpublishedChanges: true,
    }
    return store.conciergeConfiguration
  },

  async publish() {
    await delay()
    const publishedAt = new Date().toISOString()
    store.conciergeConfiguration = {
      ...store.conciergeConfiguration,
      hasUnpublishedChanges: false,
      lastPublishedAt: publishedAt,
    }
    // The header status card reports the same moment (PRD §6.2).
    store.conciergeStatus.lastConfigurationChangeAt = publishedAt
    return store.conciergeConfiguration
  },
}

const httpConciergeService: ConciergeService = {
  getStatus: () => http.get<ConciergeStatus>('/concierge/status'),
  pause: () => http.post<ConciergeStatus>('/concierge/pause'),
  resume: () => http.post<ConciergeStatus>('/concierge/resume'),
  getConfiguration: () => http.get<ConciergeConfiguration>('/concierge/configuration'),
  saveDraft: (patch) =>
    http.patch<ConciergeConfiguration>('/concierge/configuration', patch),
  publish: () => http.post<ConciergeConfiguration>('/concierge/configuration/publish'),
}

export const conciergeService: ConciergeService = USE_MOCKS
  ? mockConciergeService
  : httpConciergeService
