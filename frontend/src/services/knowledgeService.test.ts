import { beforeEach, describe, expect, it } from 'vitest'

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
