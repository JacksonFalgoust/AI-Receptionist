import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { useConversationFilters } from './useConversationFilters'

function wrapperFor(initialEntry: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
  }
}

describe('useConversationFilters', () => {
  it('starts unfiltered on page 1', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations'),
    })

    expect(result.current.state.page).toBe(1)
    expect(result.current.state.range).toBe('any')
    expect(result.current.activeCount).toBe(0)
    expect(result.current.params.channel).toBeUndefined()
  })

  it('reads every filter out of the URL', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor(
        '/conversations?q=refund&channel=voice&outcome=failed&escalated=true&intent=Billing%20question&location=loc_north&employee=Sam%20Rivera&page=3',
      ),
    })

    expect(result.current.state).toMatchObject({
      search: 'refund',
      channel: 'voice',
      outcome: 'failed',
      escalated: true,
      intent: 'Billing question',
      locationId: 'loc_north',
      assignedEmployee: 'Sam Rivera',
      page: 3,
    })
    expect(result.current.activeCount).toBe(7)
  })

  it('ignores values that are not part of the domain', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations?channel=carrier-pigeon&outcome=nonsense&page=-4'),
    })

    expect(result.current.state.channel).toBeUndefined()
    expect(result.current.state.outcome).toBeUndefined()
    expect(result.current.state.page).toBe(1)
  })

  it('converts a range preset into a from bound for the service', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations?range=7d'),
    })

    const sevenDaysMs = 7 * 24 * 60 * 60 * 1000
    expect(Date.now() - new Date(result.current.params.from!).getTime()).toBeCloseTo(
      sevenDaysMs,
      -3,
    )
  })

  it('sends no date bound when the range is any time', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations?range=any'),
    })

    expect(result.current.params.from).toBeUndefined()
  })

  it('returns to page 1 when a filter changes', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations?page=3'),
    })

    act(() => result.current.setFilter({ channel: 'sms' }))

    expect(result.current.state.page).toBe(1)
    expect(result.current.state.channel).toBe('sms')
  })

  it('keeps the page when only the page changes', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations?channel=sms'),
    })

    act(() => result.current.setPage(2))

    expect(result.current.state.page).toBe(2)
    expect(result.current.state.channel).toBe('sms')
  })

  it('clears everything', () => {
    const { result } = renderHook(() => useConversationFilters(), {
      wrapper: wrapperFor('/conversations?q=refund&channel=voice&page=2'),
    })

    act(() => result.current.clear())

    expect(result.current.activeCount).toBe(0)
    expect(result.current.state.page).toBe(1)
    expect(result.current.state.search).toBe('')
  })
})
