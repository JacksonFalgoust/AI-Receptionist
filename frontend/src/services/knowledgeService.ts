import { matchesSearch, nextId, paginate, sortByDesc } from '@/mocks/query'
import { MOCK_ORGANIZATION_ID } from '@/mocks/session'
import { store } from '@/mocks/store'
import type {
  Id,
  KnowledgeItem,
  KnowledgeStatus,
  KnowledgeType,
  PageRequest,
  Paginated,
} from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'
import { toQueryString } from './queryString'

export interface KnowledgeFilters {
  search?: string
  type?: KnowledgeType
  status?: KnowledgeStatus
}

export type KnowledgeListParams = KnowledgeFilters & PageRequest

export interface CreateKnowledgeInput {
  title: string
  type: KnowledgeType
  category?: string
  content?: string
  tags?: string[]
  effectiveDate?: string
  expirationDate?: string
}

export type KnowledgePatch = Partial<
  Pick<
    KnowledgeItem,
    | 'title'
    | 'type'
    | 'status'
    | 'category'
    | 'content'
    | 'tags'
    | 'effectiveDate'
    | 'expirationDate'
  >
>

/** PRD §16 / US-5.1, US-5.2. */
export interface KnowledgeService {
  list(params?: KnowledgeListParams): Promise<Paginated<KnowledgeItem>>
  get(id: Id): Promise<KnowledgeItem>
  create(input: CreateKnowledgeInput): Promise<KnowledgeItem>
  update(id: Id, patch: KnowledgePatch): Promise<KnowledgeItem>
  remove(id: Id): Promise<void>
}

function requireItem(id: Id): KnowledgeItem {
  const item = store.knowledge.find((entry) => entry.id === id)
  if (!item) {
    throw new AppError({
      kind: 'not_found',
      title: 'Knowledge item not found',
      description: 'That item no longer exists or was deleted.',
      actions: [{ label: 'Back to Knowledge', href: '/concierge/knowledge' }],
    })
  }
  return item
}

const mockKnowledgeService: KnowledgeService = {
  async list(params = {}) {
    await delay()
    const { page, pageSize, search, type, status } = params

    const matching = store.knowledge.filter((item) => {
      if (type && item.type !== type) return false
      if (status && item.status !== status) return false
      return matchesSearch(
        [item.title, item.content, item.category, item.source, item.tags.join(' ')],
        search,
      )
    })

    return paginate(sortByDesc(matching, (item) => item.updatedAt), { page, pageSize })
  },

  async get(id) {
    await delay()
    return requireItem(id)
  },

  async create(input) {
    await delay()
    const item: KnowledgeItem = {
      id: nextId('kn'),
      organizationId: MOCK_ORGANIZATION_ID,
      title: input.title,
      type: input.type,
      status: 'active',
      source: 'Manual entry',
      category: input.category,
      content: input.content,
      tags: input.tags ?? [],
      effectiveDate: input.effectiveDate,
      expirationDate: input.expirationDate,
      updatedAt: new Date().toISOString(),
    }
    store.knowledge.push(item)
    return item
  },

  async update(id, patch) {
    await delay()
    const item = requireItem(id)
    Object.assign(item, patch, { updatedAt: new Date().toISOString() })
    return item
  },

  async remove(id) {
    await delay()
    requireItem(id)
    store.knowledge = store.knowledge.filter((entry) => entry.id !== id)
  },
}

const httpKnowledgeService: KnowledgeService = {
  list: (params = {}) =>
    http.get<Paginated<KnowledgeItem>>(`/knowledge${toQueryString({ ...params })}`),
  get: (id) => http.get<KnowledgeItem>(`/knowledge/${id}`),
  create: (input) => http.post<KnowledgeItem>('/knowledge', input),
  update: (id, patch) => http.patch<KnowledgeItem>(`/knowledge/${id}`, patch),
  remove: (id) => http.delete<void>(`/knowledge/${id}`),
}

export const knowledgeService: KnowledgeService = USE_MOCKS
  ? mockKnowledgeService
  : httpKnowledgeService
