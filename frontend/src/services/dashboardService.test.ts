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
})

describe('dashboardService feeds', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns recent activity newest first, limited', async () => {
    const activity = await dashboardService.getRecentActivity(5)

    expect(activity).toHaveLength(5)
    const times = activity.map((item) => new Date(item.at).getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('returns recent escalations newest first, limited', async () => {
    const escalations = await dashboardService.getRecentEscalations(3)

    expect(escalations).toHaveLength(3)
    const times = escalations.map((item) => new Date(item.createdAt).getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('returns an empty feed rather than throwing when the store is empty', async () => {
    store.activityEvents.length = 0
    expect(await dashboardService.getRecentActivity()).toEqual([])
  })
})
