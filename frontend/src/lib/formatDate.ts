import type { IsoDateTime } from '@/types'

/**
 * Timestamp formatting for feeds, tables, and status panels. Locale is pinned
 * to en-US so output is deterministic in tests and consistent across users
 * until the product supports localised formats.
 */

const SECOND = 1000
const MINUTE = 60 * SECOND
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const WEEK = 7 * DAY

const DATE_TIME_FORMAT = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function parse(iso: IsoDateTime): Date | null {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

function plural(value: number, unit: string): string {
  return `${value} ${unit}${value === 1 ? '' : 's'} ago`
}

/** "just now" · "12 minutes ago" · "3 days ago" · an absolute date past a week. */
export function relativeTime(iso: IsoDateTime, now: number = Date.now()): string {
  const date = parse(iso)
  if (!date) return ''

  const elapsed = now - date.getTime()
  // A clock skew or a just-written record can land marginally in the future;
  // "in -1 minutes" would be worse than treating it as now.
  if (elapsed < MINUTE) return 'just now'
  if (elapsed < HOUR) return plural(Math.floor(elapsed / MINUTE), 'minute')
  if (elapsed < DAY) return plural(Math.floor(elapsed / HOUR), 'hour')
  if (elapsed < WEEK) return plural(Math.floor(elapsed / DAY), 'day')

  return DATE_TIME_FORMAT.format(date)
}

export function formatDateTime(iso: IsoDateTime): string {
  const date = parse(iso)
  return date ? DATE_TIME_FORMAT.format(date) : ''
}
