import { rangeBounds, sortByDesc, withinRange } from '@/mocks/query'
import { store } from '@/mocks/store'
import type {
  ActivityEvent,
  DateRange,
  Escalation,
  Kpi,
  OverviewSummary,
} from '@/types'

import { delay, USE_MOCKS } from './config'
import { http } from './http'
import { toQueryString } from './queryString'

/** US-2.1–2.5: everything the Overview page reads. */
export interface DashboardService {
  getOverview(range?: DateRange): Promise<OverviewSummary>
  getRecentActivity(limit?: number): Promise<ActivityEvent[]>
  getRecentEscalations(limit?: number): Promise<Escalation[]>
}

const DEFAULT_FEED_LIMIT = 8

/**
 * US-2.2 requires exactly these five, label and value only — no trend, no
 * sparkline. Computed from the conversation store rather than seeded, so the
 * Overview can never disagree with the list a user drills into.
 */
function buildKpis(range?: DateRange): Kpi[] {
  const { from, to } = rangeBounds(range)

  const conversations = store.conversations.filter((conversation) =>
    withinRange(conversation.startedAt, from, to),
  )
  const conversationIds = new Set(conversations.map((conversation) => conversation.id))

  const transactions = store.conversationActions.filter(
    (action) =>
      conversationIds.has(action.conversationId) &&
      action.status === 'success' &&
      action.action.startsWith('Create '),
  )

  return [
    { id: 'conversations_today', label: 'Conversations Today', value: conversations.length },
    {
      id: 'calls_answered',
      label: 'Calls Answered',
      value: conversations.filter((conversation) => conversation.channel === 'voice').length,
    },
    {
      id: 'requests_completed',
      label: 'Requests Completed',
      value: conversations.filter((conversation) => conversation.outcome === 'completed').length,
    },
    {
      id: 'human_escalations',
      label: 'Human Escalations',
      value: conversations.filter((conversation) => conversation.escalated).length,
    },
    { id: 'transactions_created', label: 'Transactions Created', value: transactions.length },
  ]
}

const mockDashboardService: DashboardService = {
  async getOverview(range) {
    await delay()
    return { kpis: buildKpis(range) }
  },

  async getRecentActivity(limit = DEFAULT_FEED_LIMIT) {
    await delay()
    return sortByDesc(store.activityEvents, (event) => event.at).slice(0, limit)
  },

  async getRecentEscalations(limit = DEFAULT_FEED_LIMIT) {
    await delay()
    return sortByDesc(store.escalations, (escalation) => escalation.createdAt).slice(0, limit)
  },
}

const httpDashboardService: DashboardService = {
  getOverview: (range) =>
    http.get<OverviewSummary>(
      `/dashboard/overview${toQueryString({ preset: range?.preset, from: range?.from, to: range?.to })}`,
    ),
  getRecentActivity: (limit = DEFAULT_FEED_LIMIT) =>
    http.get<ActivityEvent[]>(`/dashboard/activity${toQueryString({ limit })}`),
  getRecentEscalations: (limit = DEFAULT_FEED_LIMIT) =>
    http.get<Escalation[]>(`/dashboard/escalations${toQueryString({ limit })}`),
}

export const dashboardService: DashboardService = USE_MOCKS
  ? mockDashboardService
  : httpDashboardService
