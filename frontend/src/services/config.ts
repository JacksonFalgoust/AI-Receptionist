/**
 * Runtime switches for the service layer.
 *
 * PRD §38: the UI is built against mock services first. Flipping
 * `VITE_USE_MOCKS=false` points the same service interfaces at the real API
 * without any component changing.
 */

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'

/** Relative by default so Vite's dev proxy forwards to the FastAPI server. */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

/**
 * Artificial delay on mock responses. Without it, loading skeletons never
 * render during development and we ship untested loading states.
 */
export const MOCK_LATENCY_MS = 400

export function delay(ms: number = MOCK_LATENCY_MS): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export const SESSION_STORAGE_KEY = 'guideants.concierge.session'
