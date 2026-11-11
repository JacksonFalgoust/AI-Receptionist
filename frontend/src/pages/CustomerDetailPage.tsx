import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { Breadcrumb } from '@/components/ui/Breadcrumb'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table } from '@/components/ui/Table'
import { BOOKING_COLUMNS } from '@/features/bookings/bookingColumns'
import { paths } from '@/routes/paths'
import { customerService } from '@/services/customerService'

/** One Booqable customer: contact details and every booking they have made. */
export function CustomerDetailPage() {
  const { id = '' } = useParams()

  const query = useQuery({
    queryKey: ['customers', 'detail', id],
    queryFn: () => customerService.get(id),
  })

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-3">
        <Breadcrumb
          items={[
            { label: 'Customers', href: paths.customers },
            { label: query.data?.customer.name ?? id },
          ]}
        />
      </div>
      <QueryBoundary query={query} skeletonRows={6}>
        {({ customer, bookings }) => (
          <>
            <PageHeader
              title={customer.name ?? 'Unnamed customer'}
              description={[customer.email, customer.phone].filter(Boolean).join(' · ') || 'No contact details'}
              actions={
                <a
                  href={customer.booqableUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-brand-ink hover:underline"
                >
                  Open in Booqable
                </a>
              }
            />
            <Panel data-testid="customer-bookings-panel">
              <PanelHeader title={`Bookings (${bookings.length})`} />
              {bookings.length === 0 ? (
                <p className="px-4 py-6 text-sm text-ink-muted">This customer has no bookings yet.</p>
              ) : (
                <Table
                  columns={BOOKING_COLUMNS}
                  rows={bookings}
                  getRowId={(booking) => booking.id}
                  frame={false}
                />
              )}
            </Panel>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}
