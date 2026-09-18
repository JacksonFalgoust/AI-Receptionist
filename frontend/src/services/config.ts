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
 * render during development and we ship untested loading states. Zeroed under
 * Vitest, where it would only add dead time to every service test.
 */
export const MOCK_LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 400

export function delay(ms: number = MOCK_LATENCY_MS): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export const SESSION_STORAGE_KEY = 'guideants.concierge.session'

/**
 * `VITE_USE_MOCKS=false` used to be all-or-nothing -- every one of the
 * thirteen services in this directory switching to its HTTP implementation
 * at once. E6 ships one service at a time instead: `VITE_LIVE_SERVICES`
 * names which services go live while the rest keep using mocks. Once every
 * service has migrated, this and USE_MOCKS can both retire.
 */
const LIVE_SERVICES = new Set(
  (import.meta.env.VITE_LIVE_SERVICES ?? '')
    .split(',')
    .map((service) => service.trim())
    .filter(Boolean),
)

export function isLive(service: string): boolean {
  return !USE_MOCKS || LIVE_SERVICES.has(service)
}
