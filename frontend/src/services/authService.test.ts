import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * `vi.stubGlobal` (not a direct `global.fetch = ...` assignment) so the mock
 * -- which only implements the `{status, ok, json}` shape http.ts actually
 * reads, not the full `Response` interface -- doesn't fail `npm run
 * typecheck` by being assigned somewhere typed as `typeof fetch`.
 */
describe('httpAuthService', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCKS', 'false')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('posts credentials to /api/auth/login and persists the session', async () => {
    const session = {
      token: 'tok_abc',
      user: {
        id: 'owner',
        name: 'Owner',
        email: 'admin@example.com',
        role: 'owner',
        organizationId: 'org_default',
        organizationName: 'Default Organization',
      },
      expiresAt: '2026-09-14T12:00:00Z',
    }
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => session,
    })
    vi.stubGlobal('fetch', fetchMock)

    vi.resetModules()
    const { authService } = await import('./authService')
    const result = await authService.signIn({ email: 'admin@example.com', password: 'secret' })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'admin@example.com', password: 'secret' }),
      }),
    )
    expect(result.token).toBe('tok_abc')
    expect(localStorage.getItem('guideants.concierge.session')).toContain('tok_abc')
  })

  it('maps a 422 login failure to a validation AppError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 422,
        ok: false,
        json: async () => ({ detail: 'Invalid email or password' }),
      }),
    )

    vi.resetModules()
    const { authService } = await import('./authService')

    await expect(
      authService.signIn({ email: 'admin@example.com', password: 'wrong' }),
    ).rejects.toMatchObject({ kind: 'validation' })
  })
})
