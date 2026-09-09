import type { DateRangePreset, IsoDateTime } from '@/types'

const DAY_MS = 24 * 60 * 60 * 1000

const WINDOWS: Record<'today' | '7d' | '30d', number> = {
  today: DAY_MS,
  '7d': 7 * DAY_MS,
  '30d': 30 * DAY_MS,
}

/**
 * The single place a preset becomes concrete bounds. Lives in `lib/` rather
 * than `mocks/` because the Conversations page needs it too, and PRD §38 bars
 * non-service modules from importing the mock layer.
 *
 * `today` is a rolling 24-hour window, not since-midnight — carried over from
 * the original `rangeBounds` so KPI numbers do not shift underneath B1.
 */
export function presetBounds(
  preset: DateRangePreset,
  from?: IsoDateTime,
  to?: IsoDateTime,
): { from?: IsoDateTime; to?: IsoDateTime } {
  if (preset === 'custom') return { from, to }
  return { from: new Date(Date.now() - WINDOWS[preset]).toISOString() }
}
