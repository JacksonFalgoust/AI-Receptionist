import { Link } from 'react-router-dom'

import { StatusPill } from '@/components/ui/StatusPill'
import type { TableColumn } from '@/components/ui/Table'
import { formatDateTime } from '@/lib/formatDate'
import { knowledgeTypeLabel } from '@/lib/knowledgeLabels'
import { paths } from '@/routes/paths'
import type { KnowledgeItem } from '@/types'

/**
 * PRD §16.2 / US-5.1's six columns, in the story's order. Kept out of the page
 * so C2's editor can reuse the same type and status renderers rather than
 * labelling a type a second, subtly different way.
 *
 * No column declares `sortValue` — see `conversationColumns` for why a
 * page-local sort control would misrepresent itself.
 */
export const KNOWLEDGE_COLUMNS: TableColumn<KnowledgeItem>[] = [
  {
    id: 'title',
    header: 'Name',
    render: (item) => (
      <Link
        to={paths.knowledgeItem(item.id)}
        className="font-medium text-brand-ink hover:underline"
      >
        {item.title}
      </Link>
    ),
  },
  {
    id: 'type',
    header: 'Type',
    render: (item) => <span className="whitespace-nowrap">{knowledgeTypeLabel(item.type)}</span>,
  },
  {
    id: 'status',
    header: 'Status',
    render: (item) => <StatusPill status={item.status} />,
  },
  {
    id: 'source',
    header: 'Source',
    // An uploaded filename or a URL, both of which run long next to "Manual
    // entry"; the table scrolls horizontally rather than wrapping mid-word.
    render: (item) => <span className="text-ink-secondary">{item.source}</span>,
  },
  {
    id: 'updatedAt',
    header: 'Updated',
    render: (item) => (
      <span className="whitespace-nowrap text-ink-secondary">{formatDateTime(item.updatedAt)}</span>
    ),
  },
  {
    id: 'actions',
    header: 'Actions',
    render: (item) => {
      // An item still being read cannot be edited yet, so the label says what
      // the editor will actually offer. Both lead to the same screen.
      const verb = item.status === 'processing' ? 'View' : 'Edit'
      return (
        <Link
          to={paths.knowledgeItem(item.id)}
          // The visible label is the verb alone; the accessible name carries
          // the title, so a screen reader hears which item it acts on rather
          // than a column of identical "Edit" links.
          aria-label={`${verb} ${item.title}`}
          className="inline-flex items-center rounded-md border border-border px-2 py-1 text-xs font-semibold text-ink-secondary hover:bg-canvas-tint"
        >
          {verb}
        </Link>
      )
    },
  },
]
