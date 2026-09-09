import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore, store } from '@/mocks/store'

import { analyticsService } from './analyticsService'

describe('analyticsService.getSummary', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns exactly the three KPIs US-4.1 allows', async () => {
    const summary = await analyticsService.getSummary({ preset: '30d' })

    expect(summary.kpis.map((kpi) => kpi.label)).toEqual([
      'Total conversations',
      'Escalation rate',
      'Avg duration',
    ])
  })

  it('formats the escalation rate as a percent and duration as a duration', async () => {
    const summary = await analyticsService.getSummary({ preset: '30d' })

    expect(summary.kpis[1].format).toBe('percent')
    expect(summary.kpis[2].format).toBe('duration')
  })

  it('computes the escalation rate from the conversations in range', async () => {
    const summary = await analyticsService.getSummary({ preset: '30d' })
    const total = summary.kpis[0].value
    const escalated = store.conversations.filter((item) => item.escalated).length

    expect(summary.kpis[1].value).toBe(Math.round((escalated / total) * 100))
  })

  it('ranks top intents by volume, highest first, with no trend field', async () => {
    const summary = await analyticsService.getSummary({ preset: '30d' })

    expect(summary.topIntents.length).toBeGreaterThan(0)
    const volumes = summary.topIntents.map((item) => item.volume)
    expect([...volumes].sort((a, b) => b - a)).toEqual(volumes)
    expect(Object.keys(summary.topIntents[0]).sort()).toEqual(['intent', 'volume'])
  })

  it('reports channel distribution covering every channel present', async () => {
    const summary = await analyticsService.getSummary({ preset: '30d' })
    const channels = summary.channelDistribution.map((item) => item.channel).sort()

    expect(channels).toEqual(['other', 'sms', 'voice', 'web'])
    const counted = summary.channelDistribution.reduce((sum, item) => sum + item.count, 0)
    expect(counted).toBe(summary.kpis[0].value)
  })

  it('returns one volume point per day, oldest first', async () => {
    const summary = await analyticsService.getSummary({ preset: '7d' })
    const times = summary.volumeOverTime.map((point) => new Date(point.at).getTime())

    expect(times.length).toBeGreaterThan(0)
    expect([...times].sort((a, b) => a - b)).toEqual(times)
  })

  it('survives an empty range without dividing by zero', async () => {
    const summary = await analyticsService.getSummary({
      preset: 'custom',
      from: '2000-01-01T00:00:00.000Z',
      to: '2000-01-02T00:00:00.000Z',
    })

    expect(summary.kpis[0].value).toBe(0)
    expect(summary.kpis[1].value).toBe(0)
    expect(summary.kpis[2].value).toBe(0)
    expect(summary.topIntents).toEqual([])
  })
})
