import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { ActivityFeed } from '@/components/ui/ActivityFeed'
import type { ActivityItem } from '@/components/ui/ActivityFeed'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { CHANNEL_LABELS } from '@/lib/channelLabels'
import { relativeTime } from '@/lib/formatDate'
import { paths } from '@/routes/paths'
import { dashboardService } from '@/services/dashboardService'
import type { ActivityEvent, DateRange } from '@/types'

/**
 * An activity is either something done for a caller or something a connected
 * system did on its own. Naming whichever one is present keeps the middle
 * column meaningful instead of falling back to an em dash.
 */
function contextFor(event: ActivityEvent): string {
  return event.customerRef ?? event.system ?? 'Concierge'
}

function toItem(event: ActivityEvent): ActivityItem {
  return {
    id: event.id,
    time: relativeTime(event.at),
    type: event.title,
    context: contextFor(event),
    channel: event.channel ? CHANNEL_LABELS[event.channel] : 'System',
    status: event.status,
    // B7 builds the detail screen; the route already resolves, so linking now
    // costs nothing and an activity without a conversation stays plain text.
    href: event.conversationId ? paths.conversation(event.conversationId) : undefined,
  }
}

/**
 * US-2.4: what Concierge just did, so a manager can see the last few minutes
 * of work without opening the Conversations list.
 *
 * The feed is read-only and deliberately short — the service caps it. Anyone
 * who wants the whole history follows the header link.
 */
export interface RecentActivityCardProps {
  /** The Overview's date scope. Undefined means every event, newest first. */
  range?: DateRange
}

export function RecentActivityCard({ range }: RecentActivityCardProps) {
  const query = useQuery({
    queryKey: ['dashboard', 'activity', range],
    queryFn: () => dashboardService.getRecentActivity(range),
  })

  return (
    <Panel>
      <PanelHeader
        title="Recent Activity"
        action={
          <Link
            to={paths.conversations}
            className="text-sm font-semibold text-brand-ink hover:underline"
          >
            View conversations
          </Link>
        }
      />
      <div className="px-4 py-2">
        <QueryBoundary
          query={query}
          skeletonRows={6}
          isEmpty={(events) => events.length === 0}
          empty={{
            title: 'No recent activity',
            description: 'Calls and messages Concierge handles will appear here.',
          }}
        >
          {(events) => <ActivityFeed items={events.map(toItem)} />}
        </QueryBoundary>
      </div>
    </Panel>
  )
}
