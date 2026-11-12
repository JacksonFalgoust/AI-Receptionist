import '@testing-library/jest-dom/vitest'

import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

import { presetBounds } from '@/lib/dateRange'

// The mocks seed rows as "N minutes ago" from Date.now(), while the `today`
// range resets at business-timezone midnight. Run shortly after midnight and
// those "today" rows land in yesterday, so dashboard tests fail depending on
// the wall clock. Pin Date (only Date -- timers stay real) to noon on the
// business day so results never depend on when the suite runs.
const businessNoon = new Date(
  new Date(presetBounds('today').from as string).getTime() + 12 * 60 * 60 * 1000,
)

function pinClock() {
  vi.useFakeTimers({ toFake: ['Date'], now: businessNoon })
}

pinClock()
beforeEach(pinClock)

afterEach(() => {
  cleanup()
  // Services persist the session in localStorage; leaking it across tests
  // would make auth-dependent cases order-sensitive.
  localStorage.clear()
})
