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
  /**
   * `range` comes first because it is what callers actually pass — the Overview
   * cards take the page's date scope and leave `limit` at its default.
   */
  getRecentActivity(range?: DateRange, limit?: number): Promise<ActivityEvent[]>
  getRecentEscalations(range?: DateRange, limit?: number): Promise<Escalation[]>
  /**
   * US-10.1's optional summary stat on the routing page. A count rather than a
   * capped list: `getRecentEscalations` tops out at its limit, so counting its
   * result would silently cap the number too.
   */
  countEscalations(range?: DateRange): Promise<number>
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
  async getOverview(range = { preset: 'today' }) {
    await delay()
    return { kpis: buildKpis(range) }
  },

  async getRecentActivity(range, limit = DEFAULT_FEED_LIMIT) {
    await delay()
    const { from, to } = rangeBounds(range)
    const scoped = store.activityEvents.filter((event) => withinRange(event.at, from, to))
    return sortByDesc(scoped, (event) => event.at).slice(0, limit)
  },

  async getRecentEscalations(range, limit = DEFAULT_FEED_LIMIT) {
    await delay()
    const { from, to } = rangeBounds(range)
    const scoped = store.escalations.filter((escalation) =>
      withinRange(escalation.createdAt, from, to),
    )
    return sortByDesc(scoped, (escalation) => escalation.createdAt).slice(0, limit)
  },

  async countEscalations(range) {
    // Plain `delay()`, not `delay(120)`: every other explicit-latency mock in
    // this codebase is a mutation a test awaits directly (a toggle click, a
    // submit), so its delay is absorbed by that await. This is a `useQuery`
    // that fires on mount alongside `routingService.list()` — nothing in
    // RoutingPage's tests ever explicitly waits for it to settle, so a real
    // (non-test-mode) delay here is a background timer that can fire at any
    // point during a later, unrelated interaction. It intermittently did:
    // landing mid-`userEvent.click()` on another element, it re-rendered
    // `RoutingPage` (and, since `RoutingRulesTable` isn't memoized, the row
    // being clicked) out from under the click, dropping it. `delay()` alone
    // honours `MOCK_LATENCY_MS`'s test-mode override to 0, matching how
    // every sibling query in this file already behaves.
    await delay()
    const { from, to } = rangeBounds(range)
    return store.escalations.filter((escalation) =>
      withinRange(escalation.createdAt, from, to),
    ).length
  },
}

const httpDashboardService: DashboardService = {
  getOverview: (range) =>
    http.get<OverviewSummary>(
      `/dashboard/overview${toQueryString({ preset: range?.preset, from: range?.from, to: range?.to })}`,
    ),
  getRecentActivity: (range, limit = DEFAULT_FEED_LIMIT) =>
    http.get<ActivityEvent[]>(
      `/dashboard/activity${toQueryString({ limit, preset: range?.preset, from: range?.from, to: range?.to })}`,
    ),
  getRecentEscalations: (range, limit = DEFAULT_FEED_LIMIT) =>
    http.get<Escalation[]>(
      `/dashboard/escalations${toQueryString({ limit, preset: range?.preset, from: range?.from, to: range?.to })}`,
    ),
  countEscalations: (range) =>
    http.get<number>(
      `/dashboard/escalations/count${toQueryString({
        preset: range?.preset,
        from: range?.from,
        to: range?.to,
      })}`,
    ),
}

export const dashboardService: DashboardService = USE_MOCKS
  ? mockDashboardService
  : httpDashboardService
