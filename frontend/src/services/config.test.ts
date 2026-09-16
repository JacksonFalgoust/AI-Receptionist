import { afterEach, describe, expect, it, vi } from 'vitest'

describe('isLive', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('is live for every service once USE_MOCKS is false', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'false')
    vi.resetModules()
    const { isLive } = await import('./config')

    expect(isLive('conversations')).toBe(true)
    expect(isLive('anything')).toBe(true)
  })

  it('is mocked by default, with mocks on and nothing named live', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true')
    vi.stubEnv('VITE_LIVE_SERVICES', '')
    vi.resetModules()
    const { isLive } = await import('./config')

    expect(isLive('conversations')).toBe(false)
  })

  it('brings only the named services live while mocks stay on', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true')
    vi.stubEnv('VITE_LIVE_SERVICES', 'auth, conversations')
    vi.resetModules()
    const { isLive } = await import('./config')

    expect(isLive('auth')).toBe(true)
    expect(isLive('conversations')).toBe(true)
    expect(isLive('billing')).toBe(false)
  })
})
