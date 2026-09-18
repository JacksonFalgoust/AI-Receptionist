import { describe, expect, it, vi, beforeEach } from 'vitest'

import { configurationService } from './configurationService'
import { http } from './http'

vi.mock('./http', () => ({
  http: { get: vi.fn(), patch: vi.fn(), post: vi.fn() },
}))

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  isLive: (service: string) => service === 'configuration',
}))

describe('configurationService (live)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads the configuration', async () => {
    vi.mocked(http.get).mockResolvedValue({ businessProfile: { name: 'Peachtree Pedals' } })
    const result = await configurationService.getConfiguration()
    expect(http.get).toHaveBeenCalledWith('/concierge/configuration')
    expect(result.businessProfile.name).toBe('Peachtree Pedals')
  })

  it('patches a single section', async () => {
    vi.mocked(http.patch).mockResolvedValue({ hasUnpublishedChanges: true })
    await configurationService.saveDraft({ identity: { greeting: 'Hi' } } as never)
    expect(http.patch).toHaveBeenCalledWith('/concierge/configuration', {
      identity: { greeting: 'Hi' },
    })
  })

  it('previews without publishing', async () => {
    vi.mocked(http.post).mockResolvedValue({ instructions: 'You are...', changed: true })
    const result = await configurationService.preview()
    expect(http.post).toHaveBeenCalledWith('/concierge/configuration/preview')
    expect(result.changed).toBe(true)
  })

  it('surfaces a failed publish rather than treating it as success', async () => {
    vi.mocked(http.post).mockResolvedValue({
      published: false,
      status: 'failed',
      error: 'GuideAnts unreachable on import',
      warnings: [],
      configuration: { hasUnpublishedChanges: true },
    })
    const result = await configurationService.publish()
    expect(result.published).toBe(false)
    expect(result.error).toContain('unreachable')
    expect(result.configuration.hasUnpublishedChanges).toBe(true)
  })
})
