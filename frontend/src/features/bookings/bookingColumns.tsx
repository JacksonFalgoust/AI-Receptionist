import { StatusPill } from '@/components/ui/StatusPill'
import type { TableColumn } from '@/components/ui/Table'
import { formatBusinessDateTime } from '@/lib/formatDate'
import { formatMoney } from '@/lib/formatMoney'
import type { Booking, BookingLineItem } from '@/types'

/** "2 × Kayak, 1 × Paddleboard"; a bare count when the lines could not be loaded. */
export function formatRenting(items: BookingLineItem[] | null, itemCount: number | null): string {
  if (items && items.length > 0) {
    return items.map((line) => `${line.quantity ?? 1} × ${line.name ?? 'Item'}`).join(', ')
  }
  if (itemCount !== null && itemCount > 0) {
    return `${itemCount} ${itemCount === 1 ? 'item' : 'items'}`
  }
  return '—'
}

export const BOOKING_COLUMNS: TableColumn<Booking>[] = [
  {
    id: 'number',
    header: 'Booking #',
    render: (booking) => (booking.number === null ? '—' : `#${booking.number}`),
  },
  {
    id: 'customer',
    header: 'Customer',
    render: (booking) => {
      const contact = booking.customerPhone ?? booking.customerEmail
      return (
        <>
          {booking.customerName ?? 'No customer'}
          {contact && <span className="block text-xs text-ink-muted">{contact}</span>}
        </>
      )
    },
  },
  {
    id: 'renting',
    header: 'Renting',
    render: (booking) => formatRenting(booking.items, booking.itemCount),
  },
  {
    id: 'pickup',
    header: 'Pickup',
    render: (booking) => (
      <span className="whitespace-nowrap">{formatBusinessDateTime(booking.startsAt)}</span>
    ),
  },
  {
    id: 'return',
    header: 'Return',
    render: (booking) => (
      <span className="whitespace-nowrap">{formatBusinessDateTime(booking.stopsAt)}</span>
    ),
  },
  {
    id: 'total',
    header: 'Total',
    render: (booking) => formatMoney(booking.totalCents, 'USD'),
  },
  {
    id: 'payment',
    header: 'Payment',
    render: (booking) => <StatusPill status={booking.payment} />,
  },
  {
    id: 'status',
    header: 'Status',
    render: (booking) => (booking.label ? <StatusPill status={booking.label} /> : null),
  },
  {
    id: 'booqable',
    header: 'Booqable',
    visuallyHiddenHeader: true,
    render: (booking) => (
      <a
        href={booking.booqableUrl}
        target="_blank"
        rel="noreferrer"
        className="whitespace-nowrap font-medium text-brand-ink hover:underline"
      >
        Open in Booqable
      </a>
    ),
  },
]
