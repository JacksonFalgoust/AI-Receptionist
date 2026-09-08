import { store } from '@/mocks/store'
import type { Feature, Id } from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

/** PRD §14 / US-7.1. */
export interface FeatureService {
  list(): Promise<Feature[]>
  setEnabled(id: Id, enabled: boolean): Promise<Feature>
}

const BLOCKED_BY_SETUP = ['setup_required', 'connection_required', 'error'] as const

const mockFeatureService: FeatureService = {
  async list() {
    await delay()
    return [...store.features]
  },

  async setEnabled(id, enabled) {
    await delay(120)
    const feature = store.features.find((item) => item.id === id)
    if (!feature) {
      throw new AppError({
        kind: 'not_found',
        title: 'Feature not found',
        description: `That feature no longer exists (${id}).`,
      })
    }

    if (!enabled) {
      feature.status = 'disabled'
      return feature
    }

    // US-7.1: turning on something that still needs setup routes the user to
    // the next step rather than flipping a switch that cannot work.
    if ((BLOCKED_BY_SETUP as readonly string[]).includes(feature.status)) {
      throw new AppError({
        kind: 'validation',
        title: `${feature.name} needs setup first`,
        description: feature.requiredIntegrationName
          ? `Connect ${feature.requiredIntegrationName} before turning on ${feature.name}.`
          : `Finish setting up ${feature.name} before turning it on.`,
        actions: [{ label: 'View integration', href: '/integrations' }],
      })
    }

    feature.status = 'enabled'
    return feature
  },
}

const httpFeatureService: FeatureService = {
  list: () => http.get<Feature[]>('/features'),
  setEnabled: (id, enabled) => http.patch<Feature>(`/features/${id}`, { enabled }),
}

export const featureService: FeatureService = USE_MOCKS
  ? mockFeatureService
  : httpFeatureService
