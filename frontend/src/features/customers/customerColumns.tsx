import { Link } from 'react-router-dom'

import type { TableColumn } from '@/components/ui/Table'
import { formatBusinessDateTime } from '@/lib/formatDate'
import { paths } from '@/routes/paths'
import type { Customer } from '@/types'

export const CUSTOMER_COLUMNS: TableColumn<Customer>[] = [
  {
    id: 'name',
    header: 'Name',
    render: (customer) => (
      <Link
        to={paths.customer(customer.id)}
        className="font-medium text-brand-ink hover:underline"
      >
        {customer.name ?? 'Unnamed customer'}
      </Link>
    ),
  },
  { id: 'email', header: 'Email', render: (customer) => customer.email ?? '—' },
  { id: 'phone', header: 'Phone', render: (customer) => customer.phone ?? '—' },
  {
    id: 'bookings',
    header: 'Bookings',
    render: (customer) => customer.bookingCount ?? '—',
  },
  {
    id: 'last',
    header: 'Last booking',
    render: (customer) => (
      <span className="whitespace-nowrap">{formatBusinessDateTime(customer.lastBookingAt)}</span>
    ),
  },
  {
    id: 'since',
    header: 'Customer since',
    render: (customer) => (
      <span className="whitespace-nowrap">{formatBusinessDateTime(customer.createdAt)}</span>
    ),
  },
  {
    id: 'booqable',
    header: 'Booqable',
    visuallyHiddenHeader: true,
    render: (customer) => (
      <a
        href={customer.booqableUrl}
        target="_blank"
        rel="noreferrer"
        className="whitespace-nowrap font-medium text-brand-ink hover:underline"
      >
        Open in Booqable
      </a>
    ),
  },
]
