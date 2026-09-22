import type { DateRangePreset, IsoDateTime } from '@/types'

const DAY_MS = 24 * 60 * 60 * 1000

const WINDOWS: Record<'7d' | '30d', number> = {
  '7d': 7 * DAY_MS,
  '30d': 30 * DAY_MS,
}

/**
 * The business's configured timezone -- the same one app/config.py's
 * BOOQABLE_TIMEZONE uses on the backend for reservation times, default
 * America/New_York. No shared config exists between the two runtimes, so
 * this must be kept in sync by hand with
 * app/dashboard_store.py's _today_start_utc().
 */
const BUSINESS_TIMEZONE = 'America/New_York'

/**
 * BUSINESS_TIMEZONE's UTC offset, in minutes, at the given instant --
 * computed via Intl.DateTimeFormat rather than a fixed offset, since the
 * zone observes DST and a fixed offset would drift wrong twice a year. No
 * date library is a dependency of this project.
 */
function businessTimezoneOffsetMinutes(instant: Date): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: BUSINESS_TIMEZONE,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(instant)
  const get = (type: string) => Number(parts.find((part) => part.type === type)!.value)
  const asUtc = Date.UTC(
    get('year'),
    get('month') - 1,
    get('day'),
    get('hour'),
    get('minute'),
    get('second'),
  )
  return (asUtc - instant.getTime()) / 60_000
}

/**
 * Midnight in BUSINESS_TIMEZONE for `now`, as a UTC instant. Shifts `now`
 * by the zone's current offset to read its local wall-clock date, truncates
 * to midnight, then shifts back by the same offset. The offset can be
 * wrong by up to an hour on the single calendar day a DST transition falls
 * on -- an acceptable imprecision for a KPI boundary, not worth a date
 * library to close.
 */
function businessMidnightUtc(now: Date): Date {
  const offsetMinutes = businessTimezoneOffsetMinutes(now)
  const shifted = new Date(now.getTime() + offsetMinutes * 60_000)
  const localMidnightShifted = Date.UTC(
    shifted.getUTCFullYear(),
    shifted.getUTCMonth(),
    shifted.getUTCDate(),
  )
  return new Date(localMidnightShifted - offsetMinutes * 60_000)
}

/**
 * The single place a preset becomes concrete bounds. Lives in `lib/` rather
 * than `mocks/` because the Conversations page needs it too, and PRD §38 bars
 * non-service modules from importing the mock layer.
 *
 * `today` resets at midnight in BUSINESS_TIMEZONE, not a rolling 24-hour
 * window -- a call from 6pm the previous day must not count as today.
 * `7d`/`30d` stay rolling windows; only `today` had a
 * "yesterday's call shows up in today" problem to fix. Mirrored on the
 * backend by app/dashboard_store.py's range_bounds.
 */
export function presetBounds(
  preset: DateRangePreset,
  from?: IsoDateTime,
  to?: IsoDateTime,
): { from?: IsoDateTime; to?: IsoDateTime } {
  if (preset === 'custom') return { from, to }
  if (preset === 'today') return { from: businessMidnightUtc(new Date()).toISOString() }
  return { from: new Date(Date.now() - WINDOWS[preset]).toISOString() }
}
