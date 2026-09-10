import { Link } from 'react-router-dom'

import { StatusPill } from '@/components/ui/StatusPill'
import type { TableColumn } from '@/components/ui/Table'
import { formatDateTime } from '@/lib/formatDate'
import { paths } from '@/routes/paths'
import type { Workflow } from '@/types'

/**
 * PRD §15.1 / US-8.1's six columns, in the story's order. No column declares
 * `sortValue` — see `knowledgeColumns` for why a page-local sort control
 * would misrepresent itself when the underlying list isn't paginated server-side.
 */
export const WORKFLOW_COLUMNS: TableColumn<Workflow>[] = [
  {
    id: 'name',
    header: 'Name',
    render: (workflow) => (
      <Link
        to={paths.workflow(workflow.id)}
        className="font-medium text-brand-ink hover:underline"
      >
        {workflow.name}
      </Link>
    ),
  },
  {
    id: 'description',
    header: 'Description',
    render: (workflow) => (
      <span className="text-ink-secondary">{workflow.description ?? '—'}</span>
    ),
  },
  {
    id: 'status',
    header: 'Status',
    render: (workflow) => <StatusPill status={workflow.status} />,
  },
  {
    id: 'version',
    header: 'Version',
    render: (workflow) => <span className="whitespace-nowrap">{`v${workflow.version}`}</span>,
  },
  {
    id: 'executionCount',
    header: 'Executions',
    render: (workflow) => <span>{workflow.executionCount.toLocaleString('en-US')}</span>,
  },
  {
    id: 'lastUpdatedAt',
    header: 'Updated',
    render: (workflow) => (
      <span className="whitespace-nowrap text-ink-secondary">
        {formatDateTime(workflow.lastUpdatedAt)}
      </span>
    ),
  },
]
