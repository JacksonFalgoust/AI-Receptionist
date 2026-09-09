import { useQuery } from '@tanstack/react-query'

import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table } from '@/components/ui/Table'
import type { TableColumn } from '@/components/ui/Table'
import { analyticsService } from '@/services/analyticsService'
import type { DateRange, IntentVolume } from '@/types'

/**
 * US-4.1: Intent and Volume, and explicitly no trend column. No `sortValue` —
 * the service already returns these busiest-first, which is the only order
 * this table is for.
 */
const COLUMNS: TableColumn<IntentVolume>[] = [
  { id: 'intent', header: 'Intent', render: (row) => row.intent },
  {
    id: 'volume',
    header: 'Volume',
    render: (row) => row.volume.toLocaleString('en-US'),
  },
]

export interface TopIntentsTableProps {
  range: DateRange
}

/** US-4.1: what customers actually called about, busiest first. */
export function TopIntentsTable({ range }: TopIntentsTableProps) {
  const query = useQuery({
    queryKey: ['analytics', 'summary', range],
    queryFn: () => analyticsService.getSummary(range),
  })

  return (
    <Panel>
      <PanelHeader title="Top customer intents" />
      <QueryBoundary
        query={query}
        skeletonRows={5}
        isEmpty={(summary) => summary.topIntents.length === 0}
        empty={{
          title: 'No intents recorded yet',
          description: 'Once Concierge handles conversations, the reasons customers call appear here.',
        }}
      >
        {(summary) => (
          // The Panel already draws the border, so the table goes frameless.
          <Table
            columns={COLUMNS}
            rows={summary.topIntents}
            getRowId={(row) => row.intent}
            frame={false}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}
