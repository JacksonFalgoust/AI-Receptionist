import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import { KNOWLEDGE_STATUSES, KNOWLEDGE_TYPES } from '@/lib/knowledgeLabels'
import type { KnowledgeListParams } from '@/services/knowledgeService'
import type { KnowledgeStatus, KnowledgeType } from '@/types'

export interface KnowledgeFilterState {
  search: string
  type?: KnowledgeType
  status?: KnowledgeStatus
  page: number
}

/** Anything not in the domain is treated as absent — a hand-edited URL must not throw. */
function oneOf<T extends string>(value: string | null, allowed: T[]): T | undefined {
  return allowed.includes(value as T) ? (value as T) : undefined
}

/**
 * US-5.1's search and two filters, held in the URL so a view of the library
 * — "everything that needs review", say — can be bookmarked and shared, and
 * so the back button works after opening an item. Mirrors
 * `useConversationFilters`; the two differ only in which filters exist.
 */
export function useKnowledgeFilters() {
  const [params, setParams] = useSearchParams()

  const state = useMemo<KnowledgeFilterState>(() => {
    const page = Number(params.get('page'))

    return {
      search: params.get('q') ?? '',
      type: oneOf(params.get('type'), KNOWLEDGE_TYPES),
      status: oneOf(params.get('status'), KNOWLEDGE_STATUSES),
      page: Number.isInteger(page) && page > 0 ? page : 1,
    }
  }, [params])

  const activeCount = useMemo(
    () =>
      [state.search !== '', state.type !== undefined, state.status !== undefined].filter(Boolean)
        .length,
    [state],
  )

  const listParams = useMemo<KnowledgeListParams>(
    () => ({
      search: state.search || undefined,
      type: state.type,
      status: state.status,
      page: state.page,
    }),
    [state],
  )

  const write = useCallback(
    (next: KnowledgeFilterState) => {
      const search = new URLSearchParams()
      if (next.search) search.set('q', next.search)
      if (next.type) search.set('type', next.type)
      if (next.status) search.set('status', next.status)
      if (next.page > 1) search.set('page', String(next.page))
      setParams(search, { replace: true })
    },
    [setParams],
  )

  // Any filter change returns to page 1 — a narrower filter would otherwise
  // strand the reader on a page that no longer exists.
  const setFilter = useCallback(
    (patch: Partial<KnowledgeFilterState>) => write({ ...state, ...patch, page: 1 }),
    [state, write],
  )

  const setPage = useCallback((page: number) => write({ ...state, page }), [state, write])

  const clear = useCallback(() => write({ search: '', page: 1 }), [write])

  return { state, params: listParams, activeCount, setFilter, setPage, clear }
}
