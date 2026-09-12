import { EmptyState } from '@/components/ui/EmptyState'
import { StatusPill } from '@/components/ui/StatusPill'
import { Table } from '@/components/ui/Table'
import type { TableColumn } from '@/components/ui/Table'
import { formatDate } from '@/lib/formatDate'
import { formatMoney } from '@/lib/formatMoney'
import type { Invoice, IsoDateTime } from '@/types'

export interface InvoicesTableProps {
  invoices: Invoice[]
  /** Dates the first invoice when there are none yet. */
  periodEnd: IsoDateTime
}

/**
 * PRD §21's invoices. Rendered for real rather than stubbed — US-12.1 permits
 * a stub, but the seed already holds well-formed invoices and a table of real
 * rows costs no more than a placeholder.
 *
 * No Download action: invoice documents have no source in this application,
 * and D3's rule is that no PR ships a button that does nothing.
 */
export function InvoicesTable({ invoices, periodEnd }: InvoicesTableProps) {
  // A local branch rather than the page's `QueryBoundary`: the boundary covers
  // the whole overview, which is never empty, and an empty invoice list is a
  // normal state of a successful response rather than an empty response.
  if (invoices.length === 0) {
    return (
      <EmptyState
        title="No invoices yet"
        description={`Your first invoice is issued at the end of this billing period, on ${formatDate(periodEnd)}.`}
      />
    )
  }

  const columns: TableColumn<Invoice>[] = [
    {
      id: 'number',
      header: 'Invoice',
      render: (invoice) => <span className="font-medium text-ink">{invoice.number}</span>,
      sortValue: (invoice) => invoice.number,
    },
    {
      id: 'issued',
      header: 'Issued',
      render: (invoice) => formatDate(invoice.issuedAt),
      sortValue: (invoice) => invoice.issuedAt,
    },
    {
      id: 'amount',
      header: 'Amount',
      render: (invoice) => formatMoney(invoice.amountCents, invoice.currency),
      sortValue: (invoice) => invoice.amountCents,
    },
    {
      id: 'status',
      header: 'Status',
      render: (invoice) => <StatusPill status={invoice.status} />,
      sortValue: (invoice) => invoice.status,
    },
  ]

  return (
    <Table columns={columns} rows={invoices} getRowId={(invoice) => invoice.id} frame={false} />
  )
}
