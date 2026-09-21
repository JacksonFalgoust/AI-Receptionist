import { store } from '@/mocks/store'
import type { ConciergeConfiguration } from '@/types'

import { delay, isLive } from './config'
import { http } from './http'

/** Only the sections a user edits. Tenancy and publishing markers are not patchable. */
export type ConciergeConfigurationPatch = Partial<
  Pick<ConciergeConfiguration, 'businessProfile' | 'identity' | 'terminology'>
>

export interface PublishPreview {
  instructions: string
  contentHash: string
  knowledgeItemCount: number
  changed: boolean
  previousInstructions: string | null
}

/**
 * A publish can succeed at the HTTP level and still have failed to reach the
 * guide, so `published` is reported separately from the request outcome —
 * the UI must never claim success on a failed push.
 */
export interface PublishResult {
  published: boolean
  status: 'pending' | 'succeeded' | 'failed'
  publicationId: string
  warnings: string[]
  error: string | null
  configuration: ConciergeConfiguration
}

export interface Publication {
  id: string
  createdAt: string
  publishedBy: string
  contentHash: string
  knowledgeItemCount: number
  status: string
  warnings: string[]
  error: string | null
}

export interface ConfigurationService {
  getConfiguration(): Promise<ConciergeConfiguration>
  saveDraft(patch: ConciergeConfigurationPatch): Promise<ConciergeConfiguration>
  preview(): Promise<PublishPreview>
  publish(): Promise<PublishResult>
  listPublications(): Promise<Publication[]>
  /** Re-push a stored bundle. The only real undo, since every publish
   *  replaces the guide wholesale. */
  rollback(publicationId: string): Promise<PublishResult>
}

const mockConfigurationService: ConfigurationService = {
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

  async preview() {
    await delay()
    return {
      instructions: 'You are the phone receptionist for Peachtree Pedals...',
      contentHash: 'mock-hash',
      knowledgeItemCount: store.knowledge.length,
      changed: store.conciergeConfiguration.hasUnpublishedChanges,
      previousInstructions: null,
    }
  },

  async publish() {
    await delay()
    const publishedAt = new Date().toISOString()
    store.conciergeConfiguration = {
      ...store.conciergeConfiguration,
      hasUnpublishedChanges: false,
      lastPublishedAt: publishedAt,
    }
    store.conciergeStatus = {
      ...store.conciergeStatus,
      lastConfigurationChangeAt: publishedAt,
    }
    return {
      published: true,
      status: 'succeeded',
      publicationId: 'mock-publication',
      warnings: [],
      error: null,
      configuration: store.conciergeConfiguration,
    }
  },

  async listPublications() {
    await delay()
    return []
  },

  async rollback() {
    await delay()
    return {
      published: true,
      status: 'succeeded',
      publicationId: 'mock-rollback',
      warnings: [],
      error: null,
      configuration: store.conciergeConfiguration,
    }
  },
}

const httpConfigurationService: ConfigurationService = {
  getConfiguration: () => http.get<ConciergeConfiguration>('/concierge/configuration'),
  saveDraft: (patch) =>
    http.patch<ConciergeConfiguration>('/concierge/configuration', patch),
  preview: () => http.post<PublishPreview>('/concierge/configuration/preview'),
  publish: () => http.post<PublishResult>('/concierge/configuration/publish'),
  listPublications: () => http.get<Publication[]>('/concierge/publications'),
  rollback: (publicationId) =>
    http.post<PublishResult>(`/concierge/publications/${publicationId}/rollback`),
}

export const configurationService: ConfigurationService = isLive('configuration')
  ? httpConfigurationService
  : mockConfigurationService
