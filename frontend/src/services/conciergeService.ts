import { store } from '@/mocks/store'
import type { ConciergeStatus } from '@/types'

import { delay, USE_MOCKS } from './config'
import { http } from './http'

/** PRD §6.2 (status). */
export interface ConciergeService {
  getStatus(): Promise<ConciergeStatus>
  pause(): Promise<ConciergeStatus>
  resume(): Promise<ConciergeStatus>
}

/**
 * Writes replace the stored object instead of mutating it, the way a real API
 * response would. Returning the same reference the cache already holds leaves
 * React Query unable to see the change, so every other consumer of the status
 * — the header badge above all — silently keeps rendering the old state.
 */
const mockConciergeService: ConciergeService = {
  async getStatus() {
    await delay()
    return store.conciergeStatus
  },

  async pause() {
    await delay(120)
    store.conciergeStatus = { ...store.conciergeStatus, state: 'paused' }
    return store.conciergeStatus
  },

  async resume() {
    await delay(120)
    store.conciergeStatus = { ...store.conciergeStatus, state: 'active' }
    return store.conciergeStatus
  },
}

const httpConciergeService: ConciergeService = {
  getStatus: () => http.get<ConciergeStatus>('/concierge/status'),
  pause: () => http.post<ConciergeStatus>('/concierge/pause'),
  resume: () => http.post<ConciergeStatus>('/concierge/resume'),
}

export const conciergeService: ConciergeService = USE_MOCKS
  ? mockConciergeService
  : httpConciergeService
