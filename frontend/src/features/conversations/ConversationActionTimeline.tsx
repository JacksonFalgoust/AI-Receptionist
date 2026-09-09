import { EmptyState } from '@/components/ui/EmptyState'
import { Timeline } from '@/components/ui/Timeline'
import type { TimelineItem } from '@/components/ui/Timeline'
import { formatDateTime } from '@/lib/formatDate'
import type { ConversationAction } from '@/types'

/**
 * PRD §10.5: connected system, what was attempted, and how it responded.
 * Rendered verbatim — PRD §47 forbids credentials ever reaching this payload,
 * and that guarantee has to hold server-side; a filter here would only hide
 * from the page what is already in the response.
 */
function SystemDetails({ details }: { details: Record<string, string> }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-sm bg-canvas-tint p-2 text-xs">
      {Object.entries(details).map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="font-semibold text-ink-secondary">{key}</dt>
          <dd className="text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function toItem(action: ConversationAction): TimelineItem {
  return {
    id: action.id,
    time: formatDateTime(action.at),
    title: action.action,
    meta: `${action.system} · ${action.result}`,
    // Only a failure gets the error tone; pending and success both read as
    // ordinary progress on a record of something that already happened.
    tone: action.status === 'error' ? 'error' : 'default',
    details: action.details ? <SystemDetails details={action.details} /> : undefined,
  }
}

export interface ConversationActionTimelineProps {
  actions: ConversationAction[]
}

/**
 * US-3.2: what Concierge actually did, in order, and whether each step worked.
 */
export function ConversationActionTimeline({ actions }: ConversationActionTimelineProps) {
  if (actions.length === 0) {
    return (
      <EmptyState
        title="No system actions were taken"
        description="Concierge handled this conversation without calling a connected system."
      />
    )
  }

  return <Timeline items={actions.map(toItem)} />
}
