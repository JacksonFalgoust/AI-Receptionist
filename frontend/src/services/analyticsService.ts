import { rangeBounds, withinRange } from '@/mocks/query'
import { store } from '@/mocks/store'
import type {
  AnalyticsSummary,
  Channel,
  Conversation,
  DateRange,
  IntentVolume,
  Kpi,
  TimeSeriesPoint,
} from '@/types'

import { delay, USE_MOCKS } from './config'
import { http } from './http'
import { toQueryString } from './queryString'

/** US-4.1 / PRD §12. */
export interface AnalyticsService {
  getSummary(range?: DateRange): Promise<AnalyticsSummary>
}

const TOP_INTENT_LIMIT = 8

/** US-4.1 allows exactly these three. No conversion rate, no trend indicators. */
function buildKpis(conversations: Conversation[]): Kpi[] {
  const total = conversations.length
  const escalated = conversations.filter((conversation) => conversation.escalated).length
  const durations = conversations
    .map((conversation) => conversation.durationSeconds)
    .filter((seconds): seconds is number => seconds !== undefined)

  return [
    { id: 'total_conversations', label: 'Total conversations', value: total, format: 'number' },
    {
      id: 'escalation_rate',
      label: 'Escalation rate',
      // Guard the empty range: an out-of-range custom window must read 0%, not NaN.
      value: total === 0 ? 0 : Math.round((escalated / total) * 100),
      format: 'percent',
    },
    {
      id: 'avg_duration',
      label: 'Avg duration',
      value:
        durations.length === 0
          ? 0
          : Math.round(durations.reduce((sum, seconds) => sum + seconds, 0) / durations.length),
      format: 'duration',
    },
  ]
}

function buildTopIntents(conversations: Conversation[]): IntentVolume[] {
  const counts = new Map<string, number>()
  for (const conversation of conversations) {
    if (!conversation.intent) continue
    counts.set(conversation.intent, (counts.get(conversation.intent) ?? 0) + 1)
  }

  return [...counts.entries()]
    .map(([intent, volume]) => ({ intent, volume }))
    .sort((a, b) => b.volume - a.volume)
    .slice(0, TOP_INTENT_LIMIT)
}

function buildVolumeOverTime(conversations: Conversation[]): TimeSeriesPoint[] {
  const perDay = new Map<string, number>()
  for (const conversation of conversations) {
    const day = conversation.startedAt.slice(0, 10)
    perDay.set(day, (perDay.get(day) ?? 0) + 1)
  }

  return [...perDay.entries()]
    .map(([day, value]) => ({ at: `${day}T00:00:00.000Z`, value }))
    .sort((a, b) => a.at.localeCompare(b.at))
}

function buildChannelDistribution(
  conversations: Conversation[],
): { channel: Channel; count: number }[] {
  const counts = new Map<Channel, number>()
  for (const conversation of conversations) {
    counts.set(conversation.channel, (counts.get(conversation.channel) ?? 0) + 1)
  }
  return [...counts.entries()].map(([channel, count]) => ({ channel, count }))
}

const mockAnalyticsService: AnalyticsService = {
  async getSummary(range) {
    await delay()
    const { from, to } = rangeBounds(range)
    const conversations = store.conversations.filter((conversation) =>
      withinRange(conversation.startedAt, from, to),
    )

    return {
      kpis: buildKpis(conversations),
      topIntents: buildTopIntents(conversations),
      volumeOverTime: buildVolumeOverTime(conversations),
      channelDistribution: buildChannelDistribution(conversations),
    }
  },
}

const httpAnalyticsService: AnalyticsService = {
  getSummary: (range) =>
    http.get<AnalyticsSummary>(
      `/analytics/summary${toQueryString({ preset: range?.preset, from: range?.from, to: range?.to })}`,
    ),
}

export const analyticsService: AnalyticsService = USE_MOCKS
  ? mockAnalyticsService
  : httpAnalyticsService
