import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { dashboardService } from './dashboardService'

describe('dashboardService.getOverview', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns exactly the five KPIs US-2.2 requires, in order', async () => {
    const overview = await dashboardService.getOverview({ preset: 'today' })

    expect(overview.kpis.map((kpi) => kpi.label)).toEqual([
      'Conversations Today',
      'Calls Answered',
      'Requests Completed',
      'Human Escalations',
      'Transactions Created',
    ])
  })

  it('counts only conversations inside the range', async () => {
    const today = await dashboardService.getOverview({ preset: 'today' })
    const month = await dashboardService.getOverview({ preset: '30d' })

    const todayCount = today.kpis[0].value
    const monthCount = month.kpis[0].value

    expect(todayCount).toBeGreaterThan(0)
    expect(monthCount).toBeGreaterThan(todayCount)
  })

  it('counts calls answered as voice conversations only', async () => {
    const overview = await dashboardService.getOverview({ preset: '30d' })
    const voice = store.conversations.filter((item) => item.channel === 'voice').length

    expect(overview.kpis[1].value).toBe(voice)
  })

  it('counts escalations from the escalated flag', async () => {
    const overview = await dashboardService.getOverview({ preset: '30d' })
    const escalated = store.conversations.filter((item) => item.escalated).length

    expect(overview.kpis[3].value).toBe(escalated)
  })

  it('counts transactions from successful create actions', async () => {
    const overview = await dashboardService.getOverview({ preset: '30d' })
    expect(overview.kpis[4].value).toBeGreaterThan(0)
  })

  it('defaults to the "today" range when called with no argument', async () => {
    const noArg = await dashboardService.getOverview()
    const explicitToday = await dashboardService.getOverview({ preset: 'today' })

    expect(noArg.kpis[0].value).toBe(explicitToday.kpis[0].value)
  })
})

describe('dashboardService feeds', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns recent activity newest first, limited', async () => {
    const activity = await dashboardService.getRecentActivity(undefined, 5)

    expect(activity).toHaveLength(5)
    const times = activity.map((item) => new Date(item.at).getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('returns recent escalations newest first, limited', async () => {
    const escalations = await dashboardService.getRecentEscalations(undefined, 3)

    expect(escalations).toHaveLength(3)
    const times = escalations.map((item) => new Date(item.createdAt).getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('returns an empty feed rather than throwing when the store is empty', async () => {
    store.activityEvents.length = 0
    expect(await dashboardService.getRecentActivity()).toEqual([])
  })

  it('scopes recent activity to the chosen window', async () => {
    const DAY = 24 * 60 * 60 * 1000
    const template = store.activityEvents[0]
    store.activityEvents = [
      { ...template, id: 'act_today', at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
      { ...template, id: 'act_3d', at: new Date(Date.now() - 3 * DAY).toISOString() },
      { ...template, id: 'act_20d', at: new Date(Date.now() - 20 * DAY).toISOString() },
    ]

    const today = await dashboardService.getRecentActivity({ preset: 'today' })
    const week = await dashboardService.getRecentActivity({ preset: '7d' })
    const month = await dashboardService.getRecentActivity({ preset: '30d' })

    expect(today.map((event) => event.id)).toEqual(['act_today'])
    expect(week.map((event) => event.id)).toEqual(['act_today', 'act_3d'])
    expect(month.map((event) => event.id)).toEqual(['act_today', 'act_3d', 'act_20d'])
  })

  it('scopes recent escalations to the chosen window', async () => {
    const DAY = 24 * 60 * 60 * 1000
    const template = store.escalations[0]
    store.escalations = [
      { ...template, id: 'esc_today', createdAt: new Date(Date.now() - 60 * 60 * 1000).toISOString() },
      { ...template, id: 'esc_10d', createdAt: new Date(Date.now() - 10 * DAY).toISOString() },
    ]

    const today = await dashboardService.getRecentEscalations({ preset: 'today' })
    const month = await dashboardService.getRecentEscalations({ preset: '30d' })

    expect(today.map((escalation) => escalation.id)).toEqual(['esc_today'])
    expect(month.map((escalation) => escalation.id)).toEqual(['esc_today', 'esc_10d'])
  })

  it('returns the whole feed when no range is given', async () => {
    const DAY = 24 * 60 * 60 * 1000
    const template = store.activityEvents[0]
    store.activityEvents = [
      { ...template, id: 'act_recent', at: new Date().toISOString() },
      { ...template, id: 'act_ancient', at: new Date(Date.now() - 400 * DAY).toISOString() },
    ]

    expect(await dashboardService.getRecentActivity()).toHaveLength(2)
  })

  it('seeds activity across enough time that each preset shows something different', async () => {
    const today = await dashboardService.getRecentActivity({ preset: 'today' }, 100)
    const week = await dashboardService.getRecentActivity({ preset: '7d' }, 100)
    const month = await dashboardService.getRecentActivity({ preset: '30d' }, 100)

    expect(today.length).toBeGreaterThan(0)
    expect(week.length).toBeGreaterThan(today.length)
    expect(month.length).toBeGreaterThan(week.length)
  })

  it('seeds escalations across enough time that each preset shows something different', async () => {
    const today = await dashboardService.getRecentEscalations({ preset: 'today' }, 100)
    const week = await dashboardService.getRecentEscalations({ preset: '7d' }, 100)
    const month = await dashboardService.getRecentEscalations({ preset: '30d' }, 100)

    expect(today.length).toBeGreaterThan(0)
    expect(week.length).toBeGreaterThan(today.length)
    expect(month.length).toBeGreaterThan(week.length)
  })

  it('seeds every escalation against a conversation that actually escalated', async () => {
    const escalations = await dashboardService.getRecentEscalations(undefined, 100)

    for (const escalation of escalations) {
      const conversation = store.conversations.find(
        (candidate) => candidate.id === escalation.conversationId,
      )
      expect(conversation, `no conversation for ${escalation.id}`).toBeDefined()
      expect(conversation!.escalated).toBe(true)
      expect(conversation!.customerName).toBe(escalation.customerName)
    }
  })

  it('seeds every "escalated" activity event against a conversation that actually escalated', async () => {
    const activity = await dashboardService.getRecentActivity(undefined, 100)
    const escalatedEvents = activity.filter((event) => event.status === 'escalated')

    // Guards against the same seed-drift bug fixed for ESCALATIONS: a Recent
    // Activity row claiming "Escalated to team" must point at a conversation
    // whose own outcome/escalated flag agrees, or the Conversations list for
    // that same id contradicts the Overview feed.
    expect(escalatedEvents.length).toBeGreaterThan(0)
    for (const event of escalatedEvents) {
      const conversation = store.conversations.find(
        (candidate) => candidate.id === event.conversationId,
      )
      expect(conversation, `no conversation for ${event.id}`).toBeDefined()
      expect(conversation!.escalated).toBe(true)
      expect(conversation!.customerName).toBe(event.customerRef)
    }
  })
})
