import { buildBookingFixtures } from '@/mocks/bookings'
import type { Booking, Customer } from '@/types'

export function buildCustomerFixtures(): Customer[] {
  return withCounts(rawCustomers())
}

function withCounts(customers: Customer[]): Customer[] {
  const bookings = buildBookingFixtures().items
  return customers.map((c) => {
    const mine = bookings.filter((b) => b.customerName === c.name)
    const last = mine.map((b) => b.startsAt).filter(Boolean).sort().at(-1) ?? null
    return { ...c, bookingCount: mine.length, lastBookingAt: last }
  })
}

function rawCustomers(): Customer[] {
  const row = (id: number, name: string, email: string | null, phone: string | null): Customer => ({
    id: `cu_${id}`,
    name,
    email,
    phone,
    createdAt: new Date(Date.UTC(2026, 0, id)).toISOString(),
    booqableUrl: `https://example.booqable.com/customers/cu_${id}`,
    bookingCount: null,
    lastBookingAt: null,
  })
  return [
    row(1, 'Dana Whitfield', 'dana@example.com', '+15555550101'),
    row(2, 'Marcus Lee', null, '+15555550102'),
    row(3, 'Elena Rossi', 'elena@example.com', null),
    row(4, 'Tom Okafor', 'tom@example.com', '+15555550104'),
  ]
}

/** A customer's fixture bookings (matched by name), newest first, with the counts filled in. */
export function buildCustomerDetail(id: string): { customer: Customer; bookings: Booking[] } | null {
  const base = buildCustomerFixtures().find((c) => c.id === id)
  if (!base) return null
  const bookings = buildBookingFixtures()
    .items.filter((b) => b.customerName === base.name)
    .map(({ view: _view, ...booking }): Booking => booking)
    .sort((a, b) => new Date(b.startsAt ?? 0).getTime() - new Date(a.startsAt ?? 0).getTime())
  return {
    customer: { ...base, bookingCount: bookings.length, lastBookingAt: bookings[0]?.startsAt ?? null },
    bookings,
  }
}
