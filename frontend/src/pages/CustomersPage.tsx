import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pagination } from '@/components/ui/Pagination'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { SearchInput } from '@/components/ui/SearchInput'
import { Table } from '@/components/ui/Table'
import { CUSTOMER_COLUMNS } from '@/features/customers/customerColumns'
import { relativeTime } from '@/lib/formatDate'
import { useClampPage } from '@/lib/useClampPage'
import { customerService } from '@/services/customerService'

/** Read-only view of every Booqable customer. */
export function CustomersPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const rawPage = Number(params.get('page'))
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1

  const [draft, setDraft] = useState(q)

  const write = (nextQ: string, nextPage: number) => {
    const search = new URLSearchParams()
    if (nextQ) search.set('q', nextQ)
    if (nextPage > 1) search.set('page', String(nextPage))
    setParams(search, { replace: true })
  }

  // Only an explicit Refresh click bypasses the backend's short cache.
  const refreshNext = useRef(false)
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['customers', 'list', { q, page }],
    queryFn: () => {
      const refresh = refreshNext.current
      refreshNext.current = false
      return customerService.list({ q, page, refresh })
    },
  })

  useClampPage(query.data, (next) => write(q, next))

  const updated = query.data ? ` Updated ${relativeTime(query.data.fetchedAt)}.` : ''

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title="Customers"
        description={`Every customer in Booqable, read live.${updated}`}
        actions={
          <Button
            variant="ghost"
            disabled={query.isFetching}
            onClick={() => {
              refreshNext.current = true
              void queryClient.invalidateQueries({ queryKey: ['customers'] })
            }}
          >
            Refresh
          </Button>
        }
      />
      <div className="space-y-3">
        <SearchInput
          aria-label="Search customers"
          placeholder="Search by name, email, or phone"
          value={draft}
          onChange={setDraft}
          onSearch={(value) => write(value.trim(), 1)}
        />
        <Panel data-testid="customers-panel">
          <QueryBoundary
            query={query}
            skeleton="table"
            skeletonRows={8}
            isEmpty={(data) => data.total === 0}
            empty={
              q
                ? { title: 'No matching customers', description: 'Try a different name, email, or phone.' }
                : {
                    title: 'No customers yet',
                    description: 'Customers from calls or your Booqable site will appear here.',
                  }
            }
          >
            {(data) => (
              <>
                <Table
                  columns={CUSTOMER_COLUMNS}
                  rows={data.items}
                  getRowId={(customer) => customer.id}
                  frame={false}
                />
                <div className="border-t border-border px-4 py-3">
                  <Pagination
                    page={data.page}
                    pageSize={data.pageSize}
                    total={data.total}
                    onPageChange={(next) => write(q, next)}
                  />
                </div>
              </>
            )}
          </QueryBoundary>
        </Panel>
      </div>
    </div>
  )
}
