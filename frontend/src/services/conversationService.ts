import { matchesSearch, paginate, sortByDesc, withinRange } from '@/mocks/query'
import { store } from '@/mocks/store'
import type {
  Conversation,
  ConversationDetail,
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

const mockConversationService: ConversationService = {
  async list(params = {}) {
    await delay()
    const { page, pageSize, ...filters } = params
    const matching = store.conversations.filter((conversation) =>
      matchesFilters(conversation, filters),
    )
    return paginate(
      sortByDesc(matching, (conversation) => conversation.startedAt),
      { page, pageSize },
    )
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
      conversation,
      // Oldest first: a transcript and an action timeline both read forwards.
      messages: store.conversationMessages
        .filter((message) => message.conversationId === id)
        .sort((a, b) => a.at.localeCompare(b.at)),
      actions: store.conversationActions
        .filter((action) => action.conversationId === id)
        .sort((a, b) => a.at.localeCompare(b.at)),
    }
  },
}

const httpConversationService: ConversationService = {
  list: (params = {}) =>
    http.get<Paginated<Conversation>>(`/conversations${toQueryString({ ...params })}`),
  get: (id) => http.get<ConversationDetail>(`/conversations/${id}`),
}

export const conversationService: ConversationService = USE_MOCKS
  ? mockConversationService
  : httpConversationService
