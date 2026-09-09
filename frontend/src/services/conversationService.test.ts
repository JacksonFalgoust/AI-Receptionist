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

  it('attaches the escalation status to conversations that were escalated', async () => {
    const { items } = await conversationService.list({ pageSize: 100 })
    const escalated = items.find((conversation) => conversation.id === 'conv_0002')

    expect(escalated?.escalationStatus).toBe('new')
  })

  it('leaves escalationStatus undefined when no escalation exists', async () => {
    const { items } = await conversationService.list({ pageSize: 100 })
    const plain = items.find((conversation) => conversation.id === 'conv_0001')

    expect(plain?.escalationStatus).toBeUndefined()
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

describe('conversationService.listFilterOptions', () => {
  beforeEach(() => {
    resetStore()
  })

  it('offers only filter values that occur in the data', async () => {
    const options = await conversationService.listFilterOptions()

    expect(options.intents).toContain('Book appointment')
    expect(options.intents).toEqual([...options.intents].sort())
    expect(new Set(options.intents).size).toBe(options.intents.length)

    // Only the four employees who own escalated conversations, not all nine users.
    expect(options.employees).toEqual(['Avery Chen', 'Priya Shah', 'Sam Rivera', 'Taylor Brooks'])
    expect(options.locations.map((location) => location.id)).toEqual(['loc_north', 'loc_riverside'])
  })

  it('names locations rather than exposing their ids', async () => {
    const options = await conversationService.listFilterOptions()

    for (const location of options.locations) {
      expect(location.name).toBeTruthy()
      expect(location.name).not.toBe(location.id)
    }
  })
})

describe('conversation action details', () => {
  it('never seeds a credential into a system-details payload (PRD §47)', async () => {
    // US-3.2 exposes `details` verbatim on the detail screen. The guarantee has
    // to hold in the data, not in a render-time filter — by the time a secret
    // reaches the client it has already leaked.
    const FORBIDDEN = /pass(word)?|token|secret|api[-_]?key|authorization|credential/i

    for (const action of store.conversationActions) {
      for (const [key, value] of Object.entries(action.details ?? {})) {
        expect(key, `key on ${action.id}`).not.toMatch(FORBIDDEN)
        expect(value, `value on ${action.id}`).not.toMatch(FORBIDDEN)
      }
    }
  })
})
