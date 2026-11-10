import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { BookingView } from '@/types'

export function useBookingsView() {
  const [params, setParams] = useSearchParams()

  const view: BookingView = params.get('view') === 'past' ? 'past' : 'upcoming'
  const rawPage = Number(params.get('page'))
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1

  const write = useCallback(
    (nextView: BookingView, nextPage: number) => {
      const search = new URLSearchParams()
      if (nextView === 'past') search.set('view', 'past')
      if (nextPage > 1) search.set('page', String(nextPage))
      setParams(search, { replace: true })
    },
    [setParams],
  )

  const setView = useCallback((next: BookingView) => write(next, 1), [write])
  const setPage = useCallback((next: number) => write(view, next), [write, view])

  return { view, page, setView, setPage }
}
