import { useEffect } from 'react'

import type { Paginated } from '@/types'

/**
 * Corrects a requested page that is past the end of the result set — a
 * bookmarked or shared link kept after the list shrank, or a filter narrowed
 * behind it.
 *
 * Left alone, such a page reads "Page 99 of 2" over an empty table with
 * Previous stepping back one page at a time, which is 97 clicks from any
 * data. This rewrites the page to the last one that exists, so the next fetch
 * returns real rows.
 *
 * Deliberately not fixed inside `paginate`: a real paginated API returns an
 * empty page with a truthful total when asked past the end, and the mock
 * should not diverge from what E6 will actually receive. The recovery belongs
 * on the client either way.
 */
export function useClampPage<T>(
  data: Paginated<T> | undefined,
  setPage: (page: number) => void,
): void {
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1
  // An empty result set is not an out-of-range page — it has its own empty
  // state, and clamping would fight it.
  const target = data !== undefined && data.total > 0 && data.page > pageCount ? pageCount : null

  useEffect(() => {
    if (target !== null) setPage(target)
    // `setPage` is a fresh identity each render; `target` is what actually
    // decides, and it falls to null as soon as the corrected page is in
    // flight, so this cannot loop.
    // oxlint-disable-next-line exhaustive-deps
  }, [target])
}
