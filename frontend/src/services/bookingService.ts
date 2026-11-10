import { buildBookingFixtures } from '@/mocks/bookings'
import { paginate } from '@/mocks/query'
import type { Booking, BookingListParams, BookingsPage } from '@/types'

import { delay, isLive } from './config'
import { AppError, isAppError } from './errors'
import { http } from './http'
import { toQueryString } from './queryString'

/** Read-only bookings, read live from Booqable by the backend. */
export interface BookingService {
  list(params?: BookingListParams): Promise<BookingsPage>
}

const mockBookingService: BookingService = {
  async list(params = {}) {
    await delay()
    const { view = 'upcoming', page, pageSize } = params
    const { items, summary } = buildBookingFixtures()
    const time = (item: { startsAt: string | null }) => new Date(item.startsAt ?? 0).getTime()
    const matching = items
      .filter((item) => item.view === view)
      // Upcoming reads soonest first; past reads most recent first.
      .sort((a, b) => (view === 'upcoming' ? time(a) - time(b) : time(b) - time(a)))
      .map(({ view: _view, ...booking }): Booking => booking)

    return {
      ...paginate(matching, { page, pageSize }),
      summary,
      fetchedAt: new Date().toISOString(),
    }
  },
}

function booqableUnreachable(): AppError {
  return new AppError({
    kind: 'server',
    title: "Couldn't reach Booqable",
    description: 'Bookings are read live from Booqable. Try again in a moment.',
    actions: [{ label: 'Try again', retry: true }],
  })
}

export const httpBookingService: BookingService = {
  async list(params = {}) {
    try {
      return await http.get<BookingsPage>(`/bookings${toQueryString({ ...params })}`)
    } catch (error) {
      // Session expiry must still reach the auth handling.
      if (isAppError(error) && error.kind === 'unauthorized') throw error
      throw booqableUnreachable()
    }
  },
}

export const bookingService: BookingService = isLive('bookings')
  ? httpBookingService
  : mockBookingService
