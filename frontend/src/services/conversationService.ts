import { matchesSearch, paginate, sortByDesc, withinRange } from '@/mocks/query'
import { store } from '@/mocks/store'
import type {
  Conversation,
  ConversationDetail,
  ConversationFilterOptions,
  ConversationFilters,
  Id,
  PageRequest,
  Paginated,
} from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'
import { toQueryString } from './queryString'

export type ConversationListParams = ConversationFilters & PageRequest

/** PRD §9: the searchable, filterable conversation history behind US-3.1 and US-3.2. */
export interface ConversationService {
  list(params?: ConversationListParams): Promise<Paginated<Conversation>>
  get(id: Id): Promise<ConversationDetail>
  listFilterOptions(): Promise<ConversationFilterOptions>
}

function matchesFilters(
  conversation: Conversation,
  filters: ConversationFilters,
): boolean {
  if (filters.channel && conversation.channel !== filters.channel) return false
  if (filters.intent && conversation.intent !== filters.intent) return false
  if (filters.outcome && conversation.outcome !== filters.outcome) return false
  if (filters.escalated !== undefined && conversation.escalated !== filters.escalated) {
    return false
  }
  if (filters.locationId && conversation.locationId !== filters.locationId) return false
  if (
    filters.assignedEmployee &&
    conversation.assignedEmployee !== filters.assignedEmployee
  ) {
    return false
  }
  if (!withinRange(conversation.startedAt, filters.from, filters.to)) return false

  // US-3.1: search covers name, phone, conversation id, intent, and the summary.
  return matchesSearch(
    [
      conversation.customerName,
      conversation.customerPhone,
      conversation.id,
      conversation.intent,
      conversation.summary,
    ],
    filters.search,
  )
}

/** Sorted, de-duplicated, and never including an absent value. */
function distinct(values: (string | undefined)[]): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort()
}

/**
 * The escalation record is a separate collection keyed by conversation, so the
 * list joins it on rather than the store duplicating the status.
 */
function withEscalationStatus(conversation: Conversation): Conversation {
  const escalation = store.escalations.find(
    (candidate) => candidate.conversationId === conversation.id,
  )
  return escalation ? { ...conversation, escalationStatus: escalation.status } : conversation
}

const mockConversationService: ConversationService = {
  async list(params = {}) {
    await delay()
    const { page, pageSize, ...filters } = params
    const matching = store.conversations.filter((conversation) =>
      matchesFilters(conversation, filters),
    )
    const paginated = paginate(
      sortByDesc(matching, (conversation) => conversation.startedAt),
      { page, pageSize },
    )
    // Join after slicing: only the rows actually rendered need the lookup.
    return { ...paginated, items: paginated.items.map(withEscalationStatus) }
  },

  async get(id) {
    await delay()
    const conversation = store.conversations.find((item) => item.id === id)
    if (!conversation) {
      throw new AppError({
        kind: 'not_found',
        title: 'Conversation not found',
        description: 'That conversation no longer exists or was moved.',
        actions: [{ label: 'Back to conversations', href: '/conversations' }],
      })
    }

    return {
      conversation: withEscalationStatus(conversation),
      // Oldest first: a transcript and an action timeline both read forwards.
      messages: store.conversationMessages
        .filter((message) => message.conversationId === id)
        .sort((a, b) => a.at.localeCompare(b.at)),
      actions: store.conversationActions
        .filter((action) => action.conversationId === id)
        .sort((a, b) => a.at.localeCompare(b.at)),
    }
  },

  async listFilterOptions() {
    await delay()
    const locationIds = distinct(store.conversations.map((c) => c.locationId))
    const named = store.organizations.flatMap((organization) => organization.locations)

    return {
      intents: distinct(store.conversations.map((conversation) => conversation.intent)),
      employees: distinct(store.conversations.map((conversation) => conversation.assignedEmployee)),
      // Derived from conversations so no option can return nothing, but named
      // from the organization so the dropdown never shows a raw id.
      locations: locationIds.map((id) => ({
        id,
        name: named.find((location) => location.id === id)?.name ?? id,
      })),
    }
  },
}

const httpConversationService: ConversationService = {
  list: (params = {}) =>
    http.get<Paginated<Conversation>>(`/conversations${toQueryString({ ...params })}`),
  get: (id) => http.get<ConversationDetail>(`/conversations/${id}`),
  listFilterOptions: () => http.get<ConversationFilterOptions>('/conversations/filter-options'),
}

export const conversationService: ConversationService = USE_MOCKS
  ? mockConversationService
  : httpConversationService
