import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { StatusPill } from '@/components/ui/StatusPill'
import { Table } from '@/components/ui/Table'
import type { TableColumn } from '@/components/ui/Table'
import { relativeTime } from '@/lib/formatDate'
import { paths } from '@/routes/paths'
import { dashboardService } from '@/services/dashboardService'
import type { Escalation } from '@/types'

/**
 * US-2.5's five columns, in the story's order. No `sortValue` anywhere: this is
 * a short summary of the most recent escalations, already newest-first from the
 * service. Re-sorting belongs to D3's routing table, which shows all of them.
 */
const COLUMNS: TableColumn<Escalation>[] = [
  {
    id: 'customer',
    header: 'Customer',
    // B7 builds the transcript; the route resolves today, and the transcript is
    // where "why did this escalate" is actually answered.
    render: (escalation) =>
      escalation.conversationId ? (
        <Link
          to={paths.conversation(escalation.conversationId)}
          className="font-medium text-brand-ink hover:underline"
        >
          {escalation.customerName}
        </Link>
      ) : (
        <span className="font-medium text-ink">{escalation.customerName}</span>
      ),
  },
  {
    id: 'time',
    header: 'Time',
    render: (escalation) => (
      <span className="whitespace-nowrap text-ink-secondary">
        {relativeTime(escalation.createdAt)}
      </span>
    ),
  },
  { id: 'reason', header: 'Reason', render: (escalation) => escalation.reason },
  {
    id: 'assigned',
    header: 'Assigned',
    // An unowned escalation is the one a manager most needs to see, so it says
    // so rather than leaving the cell blank.
    render: (escalation) =>
      escalation.assignedTo ?? <span className="text-ink-muted">Unassigned</span>,
  },
  {
    id: 'status',
    header: 'Status',
    render: (escalation) => <StatusPill status={escalation.status} />,
  },
]

/**
 * US-2.5: where humans are needed. Read-only — assigning and resolving live in
 * Escalation & Routing, which the header links to.
 */
export function RecentEscalationsCard() {
  const query = useQuery({
    queryKey: ['dashboard', 'escalations'],
    queryFn: () => dashboardService.getRecentEscalations(),
  })

  return (
    <Panel>
      <PanelHeader
        title="Recent Escalations"
        action={
          <Link
            to={paths.routing}
            className="text-sm font-semibold text-brand-ink hover:underline"
          >
            Manage routing
          </Link>
        }
      />
      <QueryBoundary
        query={query}
        skeletonRows={5}
        isEmpty={(escalations) => escalations.length === 0}
        empty={{
          title: 'No recent escalations',
          description: 'Conversations that need a person will appear here.',
        }}
      >
        {(escalations) => (
          // The Panel already draws the border, so the table goes frameless.
          <Table
            columns={COLUMNS}
            rows={escalations}
            getRowId={(escalation) => escalation.id}
            frame={false}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}
