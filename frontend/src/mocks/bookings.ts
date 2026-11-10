import type { Booking, BookingSummary, BookingView } from '@/types'

const HOUR = 3_600_000
const DAY = 24 * HOUR

type Fixture = Booking & { view: BookingView }

/** Booking fixtures dated relative to `now`, so the page always has "today" and "overdue" rows. */
export function buildBookingFixtures(now: number = Date.now()): {
  items: Fixture[]
  summary: BookingSummary
} {
  const at = (offset: number) => new Date(now + offset).toISOString()
  const base = (id: number): Pick<Booking, 'id' | 'number' | 'booqableUrl'> => ({
    id: `bk_${id}`,
    number: 1000 + id,
    booqableUrl: `https://example.booqable.com/orders/bk_${id}`,
  })

  const items: Fixture[] = [
    {
      ...base(1), view: 'upcoming', label: null,
      customerName: 'Dana Whitfield', customerPhone: '+15555550101', customerEmail: 'dana@example.com',
      items: [{ name: 'Tandem kayak', quantity: 2 }], itemCount: 2,
      startsAt: at(2 * HOUR), stopsAt: at(2 * HOUR + 4 * HOUR),
      totalCents: 24000, payment: 'paid',
    },
    {
      ...base(2), view: 'upcoming', label: null,
      customerName: 'Marcus Lee', customerPhone: null, customerEmail: null,
      items: null, itemCount: 3,
      startsAt: at(DAY + HOUR), stopsAt: at(DAY + 5 * HOUR),
      totalCents: 18000, payment: 'unpaid',
    },
    {
      ...base(3), view: 'upcoming', label: 'out_now',
      customerName: 'Priya Natarajan', customerPhone: '+15555550103', customerEmail: 'priya@example.com',
      items: [{ name: 'Paddle board', quantity: 1 }, { name: 'Life vest', quantity: 1 }], itemCount: 2,
      startsAt: at(-2 * HOUR), stopsAt: at(3 * HOUR),
      totalCents: 9500, payment: 'paid',
    },
    {
      ...base(4), view: 'upcoming', label: 'overdue',
      customerName: 'Tom Okafor', customerPhone: '+15555550104', customerEmail: 'tom@example.com',
      items: [{ name: 'Canoe', quantity: 1 }], itemCount: 1,
      startsAt: at(-DAY - 4 * HOUR), stopsAt: at(-HOUR),
      totalCents: 12000, payment: 'partly_paid',
    },
    {
      ...base(5), view: 'past', label: 'returned',
      customerName: 'Elena Rossi', customerPhone: '+15555550105', customerEmail: 'elena@example.com',
      items: [{ name: 'Tandem kayak', quantity: 1 }], itemCount: 1,
      startsAt: at(-3 * DAY), stopsAt: at(-3 * DAY + 4 * HOUR),
      totalCents: 12000, payment: 'paid',
    },
    {
      ...base(6), view: 'past', label: 'canceled',
      customerName: 'Sam Carter', customerPhone: '+15555550106', customerEmail: null,
      items: [{ name: 'Paddle board', quantity: 2 }], itemCount: 2,
      startsAt: at(-5 * DAY), stopsAt: at(-5 * DAY + 4 * HOUR),
      totalCents: 15000, payment: 'unpaid',
    },
    {
      ...base(7), view: 'past', label: 'not_picked_up',
      customerName: 'Jules Moreau', customerPhone: null, customerEmail: 'jules@example.com',
      items: [{ name: 'Canoe', quantity: 1 }], itemCount: 1,
      startsAt: at(-7 * DAY), stopsAt: at(-7 * DAY + 4 * HOUR),
      totalCents: 8000, payment: 'paid',
    },
  ]

  return { items, summary: { pickupsToday: 1, returnsToday: 1, next7Days: 2, unpaid: 2 } }
}
