import { Link } from 'react-router-dom'

import { StatusPill } from '@/components/ui/StatusPill'
import type { TableColumn } from '@/components/ui/Table'
import { CHANNEL_LABELS } from '@/lib/channelLabels'
import { formatDateTime, formatDuration } from '@/lib/formatDate'
import { paths } from '@/routes/paths'
import type { Conversation } from '@/types'

/**
 * US-3.1's eight columns, in the story's order. Exported separately from the
 * page so B7's detail summary can reuse the same renderers rather than
 * formatting a duration or a status a second, subtly different way.
 *
 * Sorting is offered on the two continuous columns only. The rest are
 * categorical and are better served by their filters.
 */
export const CONVERSATION_COLUMNS: TableColumn<Conversation>[] = [
  {
    id: 'startedAt',
    header: 'Date / Time',
    sortValue: (conversation) => conversation.startedAt,
    render: (conversation) => (
      <Link
        to={paths.conversation(conversation.id)}
        className="whitespace-nowrap font-medium text-brand-ink hover:underline"
      >
        {formatDateTime(conversation.startedAt)}
      </Link>
    ),
  },
  {
    id: 'customer',
    header: 'Customer',
    // A caller Concierge could not identify is a real case, not missing data.
    render: (conversation) => conversation.customerName ?? 'Unknown caller',
  },
  {
    id: 'channel',
    header: 'Channel',
    render: (conversation) => CHANNEL_LABELS[conversation.channel],
  },
  {
    id: 'intent',
    header: 'Intent',
    render: (conversation) => conversation.intent ?? '—',
  },
  {
    id: 'outcome',
    header: 'Outcome',
    render: (conversation) => <StatusPill status={conversation.outcome} />,
  },
  {
    id: 'duration',
    header: 'Duration',
    sortValue: (conversation) => conversation.durationSeconds ?? 0,
    render: (conversation) => (
      <span className="whitespace-nowrap">{formatDuration(conversation.durationSeconds)}</span>
    ),
  },
  {
    id: 'escalated',
    header: 'Escalated',
    render: (conversation) => (conversation.escalated ? 'Yes' : 'No'),
  },
  {
    id: 'status',
    header: 'Status',
    // Where it stands now, which is a different question from how it ended.
    render: (conversation) => (
      <StatusPill status={conversation.escalationStatus ?? conversation.outcome} />
    ),
  },
]
