import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resetStore } from '@/mocks/store'

import { workflowService } from './workflowService'

describe('workflowService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists workflows most recently updated first', async () => {
    const workflows = await workflowService.list()
    const times = workflows.map((item) => new Date(item.lastUpdatedAt).getTime())

    expect(workflows.length).toBeGreaterThanOrEqual(6)
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('gets one workflow with its steps', async () => {
    const workflow = await workflowService.get('wf_booking')
    expect(workflow.name).toBe('Book an appointment')
    expect(workflow.steps.length).toBeGreaterThan(0)
  })

  it('creates a workflow as an unpublished draft', async () => {
    const created = await workflowService.create({ name: 'Answer billing questions' })

    expect(created.status).toBe('draft')
    expect(created.version).toBe(1)
    expect(created.executionCount).toBe(0)
    expect(created.steps).toEqual([])
    expect((await workflowService.list()).some((item) => item.id === created.id)).toBe(true)
  })

  it('saveDraft never changes status or version (PRD §13.4)', async () => {
    const before = await workflowService.get('wf_booking')

    const draft = await workflowService.saveDraft('wf_booking', {
      description: 'Updated description.',
    })

    expect(draft.description).toBe('Updated description.')
    expect(draft.status).toBe(before.status)
    expect(draft.version).toBe(before.version)
  })

  it('publish activates the workflow and bumps the version', async () => {
    const before = await workflowService.get('wf_onboarding')
    expect(before.status).toBe('draft')

    const published = await workflowService.publish('wf_onboarding')

    expect(published.status).toBe('active')
    expect(published.version).toBe(before.version + 1)
  })

  it('removes a workflow', async () => {
    await workflowService.remove('wf_survey')
    expect((await workflowService.list()).some((item) => item.id === 'wf_survey')).toBe(false)
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(workflowService.get('wf_missing')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})

describe('httpWorkflowService (VITE_LIVE_SERVICES=workflows)', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function loadLive(response: { status: number; ok: boolean; json: () => Promise<unknown> }) {
    // Mocks stay on globally; only workflows is named live.
    vi.stubEnv('VITE_USE_MOCKS', 'true')
    vi.stubEnv('VITE_LIVE_SERVICES', 'workflows')
    vi.resetModules()
    const fetchMock = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('fetch', fetchMock)
    const { workflowService: service } = await import('./workflowService')
    return { service, fetchMock }
  }

  it('lists with a bare GET', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => [],
    })

    await service.list()

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/workflows'), expect.anything())
  })

  it('creates with a JSON POST body', async () => {
    const { service, fetchMock } = await loadLive({
      status: 201,
      ok: true,
      json: async () => ({ id: 'wf_1' }),
    })

    await service.create({ name: 'New rental intake' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/workflows$/)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ name: 'New rental intake' })
  })

  it('publishes with a bodyless POST to the publish path', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => ({ id: 'wf_1', status: 'active' }),
    })

    await service.publish('wf_1')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/workflows\/wf_1\/publish$/)
    expect(init.method).toBe('POST')
  })

  it('sends an explicit null when a saveDraft patch mentions description as undefined', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => ({ id: 'wf_1' }),
    })

    await service.saveDraft('wf_1', { description: undefined })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).toHaveProperty('description', null)
  })

  it('leaves description absent when a saveDraft patch never mentions it', async () => {
    const { service, fetchMock } = await loadLive({
      status: 200,
      ok: true,
      json: async () => ({ id: 'wf_1' }),
    })

    await service.saveDraft('wf_1', { steps: [] })

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).not.toHaveProperty('description')
    expect(body).toEqual({ steps: [] })
  })
})
