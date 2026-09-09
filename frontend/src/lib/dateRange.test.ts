import { describe, expect, it } from 'vitest'

import { presetBounds } from './dateRange'

const DAY_MS = 24 * 60 * 60 * 1000

describe('presetBounds', () => {
  it('opens a one-day window for today', () => {
    const { from, to } = presetBounds('today')
    expect(to).toBeUndefined()
    expect(Date.now() - new Date(from!).getTime()).toBeCloseTo(DAY_MS, -3)
  })

  it('opens a seven-day window for 7d', () => {
    const { from } = presetBounds('7d')
    expect(Date.now() - new Date(from!).getTime()).toBeCloseTo(7 * DAY_MS, -3)
  })

  it('opens a thirty-day window for 30d', () => {
    const { from } = presetBounds('30d')
    expect(Date.now() - new Date(from!).getTime()).toBeCloseTo(30 * DAY_MS, -3)
  })

  it('passes explicit bounds straight through for custom', () => {
    expect(presetBounds('custom', '2026-01-01T00:00:00.000Z', '2026-02-01T00:00:00.000Z')).toEqual({
      from: '2026-01-01T00:00:00.000Z',
      to: '2026-02-01T00:00:00.000Z',
    })
  })
})
