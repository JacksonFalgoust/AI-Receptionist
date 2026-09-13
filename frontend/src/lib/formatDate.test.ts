import { describe, expect, it } from 'vitest'

import { formatDate, formatDateRange, formatDateTime, formatDuration, relativeTime } from './formatDate'

const NOW = new Date('2026-09-08T12:00:00.000Z').getTime()

function ago(ms: number): string {
  return new Date(NOW - ms).toISOString()
}

const SECOND = 1000
const MINUTE = 60 * SECOND
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

describe('relativeTime', () => {
  it('reads "just now" under a minute', () => {
    expect(relativeTime(ago(20 * SECOND), NOW)).toBe('just now')
  })

  it('reads minutes, singular and plural', () => {
    expect(relativeTime(ago(1 * MINUTE), NOW)).toBe('1 minute ago')
    expect(relativeTime(ago(12 * MINUTE), NOW)).toBe('12 minutes ago')
  })

  it('reads hours, singular and plural', () => {
    expect(relativeTime(ago(1 * HOUR), NOW)).toBe('1 hour ago')
    expect(relativeTime(ago(5 * HOUR), NOW)).toBe('5 hours ago')
  })

  it('reads days, singular and plural', () => {
    expect(relativeTime(ago(1 * DAY), NOW)).toBe('1 day ago')
    expect(relativeTime(ago(3 * DAY), NOW)).toBe('3 days ago')
  })

  it('falls back to an absolute date beyond a week', () => {
    const result = relativeTime(ago(30 * DAY), NOW)
    expect(result).not.toMatch(/ago$/)
    expect(result).toContain('2026')
  })

  it('treats a future timestamp as just now rather than showing a negative', () => {
    expect(relativeTime(new Date(NOW + 5 * MINUTE).toISOString(), NOW)).toBe('just now')
  })

  it('returns an empty string for an unparseable value', () => {
    expect(relativeTime('not-a-date', NOW)).toBe('')
  })
})

describe('formatDateTime', () => {
  it('renders a readable absolute date and time', () => {
    const result = formatDateTime('2026-09-08T12:00:00.000Z')
    expect(result).toContain('2026')
    expect(result).toMatch(/\d{1,2}:\d{2}/)
  })

  it('returns an empty string for an unparseable value', () => {
    expect(formatDateTime('not-a-date')).toBe('')
  })
})

describe('formatDuration', () => {
  it('reads as minutes and seconds', () => {
    expect(formatDuration(252)).toBe('4m 12s')
  })

  it('pads seconds so a column of durations aligns', () => {
    expect(formatDuration(125)).toBe('2m 05s')
  })

  it('keeps sub-minute calls in seconds alone', () => {
    expect(formatDuration(22)).toBe('22s')
  })

  it('returns an em dash when the duration is unknown', () => {
    expect(formatDuration(undefined)).toBe('—')
  })

  it('rolls a remainder that rounds up to 60 seconds into the next minute', () => {
    expect(formatDuration(119.6)).toBe('2m 00s')
  })

  it('rolls a sub-minute value that rounds up to 60 seconds into a full minute', () => {
    expect(formatDuration(59.6)).toBe('1m 00s')
  })
})

describe('formatDate', () => {
  it('renders a date with no clock time', () => {
    expect(formatDate('2026-08-30T14:05:00.000Z')).toBe('Aug 30, 2026')
  })

  it('returns an empty string for an unparseable value', () => {
    expect(formatDate('not-a-date')).toBe('')
  })
})

describe('formatDateRange', () => {
  it('states the year once when both ends share it', () => {
    expect(formatDateRange('2026-08-30T00:00:00.000Z', '2026-09-29T00:00:00.000Z')).toBe(
      'Aug 30 – Sep 29, 2026',
    )
  })

  it('states both years across a year boundary', () => {
    expect(formatDateRange('2026-12-15T00:00:00.000Z', '2027-01-14T00:00:00.000Z')).toBe(
      'Dec 15, 2026 – Jan 14, 2027',
    )
  })

  it('decides the same-year check from the UTC year, not the local year', () => {
    // In a western timezone (e.g. UTC-5) both instants below fall on "Dec 31" the
    // previous local day, but in UTC — which is what these dates are meant to be read
    // in, per formatDate.ts's own doc comment — they land on "Dec 31, 2026" and
    // "Jan 1, 2027": different years. getFullYear() would key off the local year and
    // could wrongly take the same-year branch (dropping the leading year); this fix
    // uses getUTCFullYear() so the decision never depends on the viewer's timezone.
    // Note: vite.config.ts pins the test runner's own TZ to UTC, so local time here
    // already equals UTC time — this assertion documents the intended UTC behavior
    // but can't actually fail on the old getFullYear() code from inside this suite.
    expect(formatDateRange('2026-12-31T22:00:00.000Z', '2027-01-01T02:00:00.000Z')).toBe(
      'Dec 31, 2026 – Jan 1, 2027',
    )
  })
})
