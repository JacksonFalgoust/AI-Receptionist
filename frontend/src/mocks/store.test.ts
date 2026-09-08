import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from './store'

describe('mock store', () => {
  beforeEach(() => {
    resetStore()
  })

  it('seeds enough conversations for pagination to be real', () => {
    expect(store.conversations.length).toBeGreaterThanOrEqual(60)
  })

  it('covers every channel and every outcome', () => {
    const channels = new Set(store.conversations.map((item) => item.channel))
    const outcomes = new Set(store.conversations.map((item) => item.outcome))

    expect([...channels].sort()).toEqual(['other', 'sms', 'voice', 'web'])
    expect([...outcomes].sort()).toEqual([
      'abandoned',
      'completed',
      'escalated',
      'failed',
      'follow_up_required',
    ])
  })

  it('places some conversations inside the last 24 hours', () => {
    const dayAgo = Date.now() - 24 * 60 * 60 * 1000
    const today = store.conversations.filter(
      (item) => new Date(item.startedAt).getTime() >= dayAgo,
    )
    expect(today.length).toBeGreaterThan(0)
  })

  it('gives every conversation messages and actions', () => {
    for (const conversation of store.conversations) {
      expect(
        store.conversationMessages.filter((m) => m.conversationId === conversation.id).length,
      ).toBeGreaterThan(0)
      expect(
        store.conversationActions.filter((a) => a.conversationId === conversation.id).length,
      ).toBeGreaterThan(0)
    }
  })

  it('never exposes credentials in action details (PRD §10.5)', () => {
    const forbidden = /password|secret|token|api[_-]?key/i
    for (const action of store.conversationActions) {
      for (const [key, value] of Object.entries(action.details ?? {})) {
        expect(forbidden.test(key)).toBe(false)
        expect(forbidden.test(value)).toBe(false)
      }
    }
  })

  it('restores mutated collections on reset', () => {
    const originalCount = store.conversations.length
    store.conversations.pop()
    store.conversations[0].intent = 'MUTATED'

    resetStore()

    expect(store.conversations).toHaveLength(originalCount)
    expect(store.conversations[0].intent).not.toBe('MUTATED')
  })

  it('scopes every conversation to the mock organization', () => {
    const orgIds = new Set(store.conversations.map((item) => item.organizationId))
    expect(orgIds.size).toBe(1)
  })

  it('covers every escalation status', () => {
    const statuses = new Set(store.escalations.map((item) => item.status))
    expect([...statuses].sort()).toEqual(['assigned', 'in_progress', 'new', 'resolved'])
  })

  it('covers every notification kind', () => {
    const kinds = new Set(store.notifications.map((item) => item.kind))
    expect([...kinds].sort()).toEqual([
      'configuration_issue',
      'escalation',
      'integration_failure',
      'security_event',
      'usage_limit',
      'workflow_error',
    ])
  })

  it('has both read and unread notifications', () => {
    expect(store.notifications.some((item) => !item.read)).toBe(true)
    expect(store.notifications.some((item) => item.read)).toBe(true)
  })

  it('covers every feature status', () => {
    const statuses = new Set(store.features.map((item) => item.status))
    expect([...statuses].sort()).toEqual([
      'connection_required',
      'disabled',
      'enabled',
      'error',
      'setup_required',
    ])
  })

  it('exposes Voice and SMS channels on the Concierge status', () => {
    const channels = store.conciergeStatus.channels.map((item) => item.channel)
    expect(channels).toEqual(['voice', 'sms'])
  })

  it('starts with configuration published and no unpublished changes', () => {
    expect(store.conciergeConfiguration.hasUnpublishedChanges).toBe(false)
    expect(store.conciergeConfiguration.lastPublishedAt).toBeDefined()
  })
})
