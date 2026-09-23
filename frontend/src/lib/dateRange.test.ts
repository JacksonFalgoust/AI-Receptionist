import { afterEach, describe, expect, it, vi } from 'vitest'

import { presetBounds } from './dateRange'

const DAY_MS = 24 * 60 * 60 * 1000

describe('presetBounds', () => {
  describe('today', () => {
    afterEach(() => {
      vi.useRealTimers()
    })

    it('resets at midnight America/New_York, not a rolling 24 hours', () => {
      // 2026-09-22T23:30:00Z is 2026-09-22 19:30 America/New_York (EDT,
      // UTC-4 in late September -- DST doesn't end until November).
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-09-22T23:30:00.000Z'))

      const { from, to } = presetBounds('today')

      // Midnight America/New_York on 2026-09-22 is 04:00 UTC the same day
      // -- not 23:30 - 24h, which is what the old rolling-window behavior
      // would have returned.
      expect(from).toBe('2026-09-22T04:00:00.000Z')
      expect(to).toBeUndefined()
    })

    it("excludes a call from 6pm the business's previous day", () => {
      // 2026-09-23T13:00:00Z is 2026-09-23 09:00 America/New_York (EDT) --
      // mid-morning "today".
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2026-09-23T13:00:00.000Z'))

      const { from } = presetBounds('today')

      // 2026-09-22 18:00 America/New_York (6pm "yesterday") is
      // 2026-09-22T22:00:00Z -- well within a rolling 24h of "now" (19
      // hours ago), but before this business day's midnight boundary.
      const lastNightsCall = new Date('2026-09-22T22:00:00.000Z')
      expect(lastNightsCall.getTime()).toBeLessThan(new Date(from!).getTime())
    })
  })

  describe('7d / 30d', () => {
    it('opens a seven-day rolling window for 7d', () => {
      const { from } = presetBounds('7d')
      expect(Date.now() - new Date(from!).getTime()).toBeCloseTo(7 * DAY_MS, -3)
    })

    it('opens a thirty-day rolling window for 30d', () => {
      const { from } = presetBounds('30d')
      expect(Date.now() - new Date(from!).getTime()).toBeCloseTo(30 * DAY_MS, -3)
    })
  })

  it('passes explicit bounds straight through for custom', () => {
    expect(presetBounds('custom', '2026-01-01T00:00:00.000Z', '2026-02-01T00:00:00.000Z')).toEqual({
      from: '2026-01-01T00:00:00.000Z',
      to: '2026-02-01T00:00:00.000Z',
    })
  })
})
