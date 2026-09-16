import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { knowledgeService } from './knowledgeService'

describe('knowledgeService.list', () => {
  beforeEach(() => {
    resetStore()
  })

  it('paginates and reports the full total', async () => {
    const page = await knowledgeService.list({ page: 1, pageSize: 5 })
    expect(page.items).toHaveLength(5)
    expect(page.total).toBe(store.knowledge.length)
  })

  it('filters by type', async () => {
    const page = await knowledgeService.list({ type: 'policy', pageSize: 100 })
    expect(page.items.length).toBeGreaterThan(0)
    expect(page.items.every((item) => item.type === 'policy')).toBe(true)
  })

  it('filters by status', async () => {
    const page = await knowledgeService.list({ status: 'needs_review', pageSize: 100 })
    expect(page.items.length).toBeGreaterThan(0)
    expect(page.items.every((item) => item.status === 'needs_review')).toBe(true)
  })

  it('searches title, content, and tags', async () => {
    expect((await knowledgeService.list({ search: 'cancellation' })).items.length).toBeGreaterThan(0)
    expect((await knowledgeService.list({ search: 'refunds' })).items.length).toBeGreaterThan(0)
    expect((await knowledgeService.list({ search: 'bank transfer' })).items.length).toBeGreaterThan(0)
  })

  it('sorts most recently updated first', async () => {
    const page = await knowledgeService.list({ pageSize: 100 })
    const times = page.items.map((item) => new Date(item.updatedAt).getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })
})

describe('knowledgeService writes', () => {
  beforeEach(() => {
    resetStore()
  })

  it('creates an item and returns it on the next read', async () => {
    const created = await knowledgeService.create({
      title: 'Do you offer remote appointments?',
      type: 'faq',
      category: 'Appointments',
      content: 'Yes — remote appointments are available by video or phone.',
      tags: ['appointments', 'remote'],
    })

    expect(created.status).toBe('active')
    expect(created.source).toBe('Manual entry')

    const found = await knowledgeService.get(created.id)
    expect(found.title).toBe('Do you offer remote appointments?')
  })

  it('accepts an explicit status and source, for a document upload created as Processing', async () => {
    const created = await knowledgeService.create({
      title: 'Client handbook 2027',
      type: 'document',
      status: 'processing',
      source: 'handbook-2027.pdf',
    })

    expect(created.status).toBe('processing')
    expect(created.source).toBe('handbook-2027.pdf')
  })

  it('updates an item and stamps updatedAt', async () => {
    const before = await knowledgeService.get('kn_0001')

    const updated = await knowledgeService.update('kn_0001', { status: 'disabled' })

    expect(updated.status).toBe('disabled')
    expect(new Date(updated.updatedAt).getTime()).toBeGreaterThanOrEqual(
      new Date(before.updatedAt).getTime(),
    )
  })

  it('removes an item', async () => {
    await knowledgeService.remove('kn_0002')
    await expect(knowledgeService.get('kn_0002')).rejects.toMatchObject({ kind: 'not_found' })
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(knowledgeService.get('kn_9999')).rejects.toMatchObject({ kind: 'not_found' })
  })
})

describe('httpKnowledgeService (VITE_LIVE_SERVICES=knowledge)', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function loadLive(response: { status: number; ok: boolean; json: () => Promise<unknown> }) {
    // Mocks stay on globally; only knowledge is named live.
    vi.stubEnv('VITE_USE_MOCKS', 'true')
    vi.stubEnv('VITE_LIVE_SERVICES', 'knowledge')
    vi.resetModules()
    const fetchMock = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('fetch', fetchMock)
    const { knowledgeService: service } = await import('./knowledgeService')
    return { service, fetchMock }
  }

  it('lists with filters serialised as a query string', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => ({ items: [], page: 1, pageSize: 20, total: 0 }),
    })

    await service.list({ type: 'policy', page: 1, pageSize: 20 })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/knowledge?type=policy&page=1&pageSize=20'),
      expect.anything(),
    )
  })

  it('creates with a JSON POST body', async () => {
    const { service, fetchMock } = await loadLive({
      status: 201,
      ok: true,
      json: async () => ({ id: 'kn_1' }),
    })

    await service.create({ title: 'Hours', type: 'faq' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/knowledge$/)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ title: 'Hours', type: 'faq' })
  })

  it('deletes with a DELETE and resolves on 204', async () => {
    const { service, fetchMock } = await loadLive({
      status: 204,
      ok: true,
      json: async () => null,
    })

    await expect(service.remove('kn_1')).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
  })

  it('maps a 404 to a not_found AppError', async () => {
    const { service } = await loadLive({
      status: 404,
      ok: false,
      json: async () => ({ detail: 'Knowledge item not found' }),
    })

    await expect(service.get('missing')).rejects.toMatchObject({ kind: 'not_found' })
  })

  it('sends an explicit null for a clearable field the caller set to undefined', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => ({ id: 'kn_1' }),
    })

    await service.update('kn_1', { category: undefined })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).toHaveProperty('category', null)
  })

  it('leaves a field the caller never mentioned fully absent from the body', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => ({ id: 'kn_1' }),
    })

    await service.update('kn_1', { title: 'x' })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).not.toHaveProperty('category')
  })
})
