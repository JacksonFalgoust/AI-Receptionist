import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { useKnowledgeFilters } from './useKnowledgeFilters'

function wrapperFor(initialEntry: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
  }
}

describe('useKnowledgeFilters', () => {
  it('starts unfiltered on page 1', () => {
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge'),
    })

    expect(result.current.state.page).toBe(1)
    expect(result.current.state.search).toBe('')
    expect(result.current.activeCount).toBe(0)
    expect(result.current.params.type).toBeUndefined()
    expect(result.current.params.status).toBeUndefined()
  })

  it('reads search, type, status and page out of the URL', () => {
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge?q=refund&type=policy&status=needs_review&page=2'),
    })

    expect(result.current.state).toEqual({
      search: 'refund',
      type: 'policy',
      status: 'needs_review',
      page: 2,
    })
    expect(result.current.activeCount).toBe(3)
  })

  it('ignores values that are not part of the domain', () => {
    // A hand-edited or stale URL must not throw or filter on nonsense.
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge?type=recipe&status=marinating&page=-2'),
    })

    expect(result.current.state.type).toBeUndefined()
    expect(result.current.state.status).toBeUndefined()
    expect(result.current.state.page).toBe(1)
    expect(result.current.activeCount).toBe(0)
  })

  it('treats an empty search param as absent, not an active filter', () => {
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge?q='),
    })

    expect(result.current.activeCount).toBe(0)
    expect(result.current.params.search).toBeUndefined()
  })

  it('returns to page 1 when a filter changes', () => {
    // A narrower filter would otherwise strand the reader on a page that no
    // longer exists.
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge?page=2'),
    })

    act(() => result.current.setFilter({ type: 'faq' }))

    expect(result.current.state.page).toBe(1)
    expect(result.current.state.type).toBe('faq')
  })

  it('keeps the filters when only the page changes', () => {
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge?type=faq'),
    })

    act(() => result.current.setPage(2))

    expect(result.current.state.page).toBe(2)
    expect(result.current.state.type).toBe('faq')
  })

  it('clears everything', () => {
    const { result } = renderHook(() => useKnowledgeFilters(), {
      wrapper: wrapperFor('/concierge/knowledge?q=refund&type=policy&status=active&page=2'),
    })

    act(() => result.current.clear())

    expect(result.current.activeCount).toBe(0)
    expect(result.current.state.page).toBe(1)
    expect(result.current.state.search).toBe('')
    expect(result.current.state.type).toBeUndefined()
  })
})
