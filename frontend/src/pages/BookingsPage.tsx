import { useQuery } from '@tanstack/react-query'
import { useRef } from 'react'

import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table } from '@/components/ui/Table'
import { Tabs } from '@/components/ui/Tabs'
import { BOOKING_COLUMNS } from '@/features/bookings/bookingColumns'
import { BookingSummaryRow, BookingSummarySkeleton } from '@/features/bookings/BookingSummaryRow'
import { useBookingsView } from '@/features/bookings/useBookingsView'
import { relativeTime } from '@/lib/formatDate'
import { useClampPage } from '@/lib/useClampPage'
import { bookingService } from '@/services/bookingService'
import type { BookingView } from '@/types'

const TABS = [
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'past', label: 'Past' },
]

const EMPTY = {
  upcoming: {
    title: 'No upcoming bookings',
    description: 'New bookings from calls or your Booqable site will appear here.',
  },
  past: { title: 'No past bookings yet' },
}

/** Read-only view of every Booqable booking. */
export function BookingsPage() {
  const { view, page, setView, setPage } = useBookingsView()

  // Only an explicit Refresh click bypasses the backend's short cache.
  const refreshNext = useRef(false)

  const query = useQuery({
    queryKey: ['bookings', 'list', { view, page }],
    queryFn: () => {
      const refresh = refreshNext.current
      refreshNext.current = false
      return bookingService.list({ view, page, refresh })
    },
  })

  useClampPage(query.data, setPage)

  const updated = query.data ? ` Updated ${relativeTime(query.data.fetchedAt)}.` : ''

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Bookings"
        description={`Every booking in Booqable, read live.${updated}`}
        actions={
          <Button
            variant="ghost"
            disabled={query.isFetching}
            onClick={() => {
              refreshNext.current = true
              void query.refetch()
            }}
          >
            Refresh
          </Button>
        }
      />
      <div className="space-y-3">
        {query.data ? <BookingSummaryRow summary={query.data.summary} /> : null}
        {query.isPending ? <BookingSummarySkeleton /> : null}

        <Tabs items={TABS} value={view} onChange={(value) => setView(value as BookingView)}>
          <Panel data-testid="bookings-panel">
            <QueryBoundary
              query={query}
              skeleton="table"
              skeletonRows={8}
              isEmpty={(data) => data.total === 0}
              empty={EMPTY[view]}
            >
              {(data) => (
                <>
                  <Table
                    columns={BOOKING_COLUMNS}
                    rows={data.items}
                    getRowId={(booking) => booking.id}
                    frame={false}
                  />
                  <div className="border-t border-border px-4 py-3">
                    <Pagination
                      page={data.page}
                      pageSize={data.pageSize}
                      total={data.total}
                      onPageChange={setPage}
                    />
                  </div>
                </>
              )}
            </QueryBoundary>
          </Panel>
        </Tabs>
      </div>
    </div>
  )
}
