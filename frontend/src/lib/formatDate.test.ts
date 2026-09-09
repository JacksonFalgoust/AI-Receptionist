import { describe, expect, it } from 'vitest'

import { formatDateTime, formatDuration, relativeTime } from './formatDate'

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
})
