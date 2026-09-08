import type { IsoDateTime, PageRequest, Paginated } from '@/types'

/**
 * Filtering and pagination shared by every mock service, so thirteen modules
 * do not each reinvent them and list UIs are exercised against real slicing
 * rather than a hard-coded first page.
 */

export const DEFAULT_PAGE_SIZE = 25

export function paginate<T>(
  items: T[],
  { page = 1, pageSize = DEFAULT_PAGE_SIZE }: PageRequest = {},
): Paginated<T> {
  const safePage = Math.max(1, page)
  const start = (safePage - 1) * pageSize
  return {
    items: items.slice(start, start + pageSize),
    page: safePage,
    pageSize,
    // Total is the full filtered count, never the page length — pagination
    // controls need it to know how many pages exist.
    total: items.length,
  }
}

/** True when there is no search term, or any supplied field contains it. */
export function matchesSearch(
  haystacks: (string | undefined)[],
  needle?: string,
): boolean {
  if (!needle?.trim()) return true
  const term = needle.trim().toLowerCase()
  return haystacks.some((value) => value?.toLowerCase().includes(term))
}

export function withinRange(
  at: IsoDateTime,
  from?: IsoDateTime,
  to?: IsoDateTime,
): boolean {
  const time = new Date(at).getTime()
  if (from && time < new Date(from).getTime()) return false
  if (to && time > new Date(to).getTime()) return false
  return true
}

/** Newest-first by an ISO timestamp. Returns a new array. */
export function sortByDesc<T>(items: T[], key: (item: T) => string): T[] {
  return [...items].sort((a, b) => key(b).localeCompare(key(a)))
}

let idCounter = 0

/** Sequential ids for records created through a mock service. */
export function nextId(prefix: string): string {
  idCounter += 1
  return `${prefix}_${idCounter.toString().padStart(4, '0')}`
}

/** Called by `resetStore()` so tests see identical ids run to run. */
export function resetIds(): void {
  idCounter = 0
}
