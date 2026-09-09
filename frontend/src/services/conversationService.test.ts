import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { conversationService } from './conversationService'

describe('conversationService.list', () => {
  beforeEach(() => {
    resetStore()
  })

  it('paginates, reporting the full total', async () => {
    const page = await conversationService.list({ page: 1, pageSize: 10 })
    expect(page.items).toHaveLength(10)
    expect(page.page).toBe(1)
    expect(page.total).toBe(store.conversations.length)
  })

  it('returns a different slice on page two', async () => {
    const first = await conversationService.list({ page: 1, pageSize: 10 })
    const second = await conversationService.list({ page: 2, pageSize: 10 })
    expect(second.items[0].id).not.toBe(first.items[0].id)
  })

  it('sorts newest first', async () => {
    const page = await conversationService.list({ pageSize: 20 })
    const times = page.items.map((item) => new Date(item.startedAt).getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('filters by channel', async () => {
    const page = await conversationService.list({ channel: 'sms', pageSize: 100 })
    expect(page.items.length).toBeGreaterThan(0)
    expect(page.items.every((item) => item.channel === 'sms')).toBe(true)
  })

  it('filters by outcome and escalated together', async () => {
    const page = await conversationService.list({
      outcome: 'escalated',
      escalated: true,
      pageSize: 100,
    })
    expect(page.items.length).toBeGreaterThan(0)
    expect(page.items.every((item) => item.outcome === 'escalated' && item.escalated)).toBe(true)
  })

  it('searches by customer name, phone, and conversation id', async () => {
    const byName = await conversationService.list({ search: 'dana', pageSize: 100 })
    expect(byName.items.every((item) => item.customerName === 'Dana Wu')).toBe(true)
    expect(byName.items.length).toBeGreaterThan(0)

    const byId = await conversationService.list({ search: 'conv_0001', pageSize: 100 })
    expect(byId.items.some((item) => item.id === 'conv_0001')).toBe(true)

    const byPhone = await conversationService.list({ search: '0142', pageSize: 100 })
    expect(byPhone.items.length).toBeGreaterThan(0)
  })

  it('filters by date range', async () => {
    const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    const page = await conversationService.list({ from: dayAgo, pageSize: 100 })

    expect(page.items.length).toBeGreaterThan(0)
    expect(page.total).toBeLessThan(store.conversations.length)
    expect(
      page.items.every((item) => new Date(item.startedAt).getTime() >= new Date(dayAgo).getTime()),
    ).toBe(true)
  })

  it('returns an empty page rather than throwing when nothing matches', async () => {
    const page = await conversationService.list({ search: 'no-such-customer' })
    expect(page.items).toEqual([])
    expect(page.total).toBe(0)
  })
})

describe('conversationService.get', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns the conversation with its messages and actions', async () => {
    const detail = await conversationService.get('conv_0001')

    expect(detail.conversation.id).toBe('conv_0001')
    expect(detail.messages.length).toBeGreaterThan(0)
    expect(detail.actions.length).toBeGreaterThan(0)
    expect(detail.messages.every((m) => m.conversationId === 'conv_0001')).toBe(true)
    expect(detail.actions.every((a) => a.conversationId === 'conv_0001')).toBe(true)
  })

  it('orders messages oldest first, as a transcript reads', async () => {
    const detail = await conversationService.get('conv_0001')
    const times = detail.messages.map((m) => new Date(m.at).getTime())
    expect([...times].sort((a, b) => a - b)).toEqual(times)
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(conversationService.get('conv_9999')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})
