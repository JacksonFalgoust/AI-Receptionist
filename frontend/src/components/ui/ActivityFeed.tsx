import { Link } from 'react-router-dom'

import type { KnownStatus } from '@/lib/statusTone'
import { EmptyState } from './EmptyState'
import { StatusPill } from './StatusPill'

export interface ActivityItem {
  id: string
  time: string
  type: string
  context: string
  channel: string
  status: KnownStatus
  href?: string
}

export interface ActivityFeedProps {
  items: ActivityItem[]
}

export function ActivityFeed({ items }: ActivityFeedProps) {
  if (items.length === 0) {
    return <EmptyState title="No recent activity" />
  }

  return (
    <ul>
      {items.map((item) => {
        const content = (
          <div className="flex items-center justify-between gap-3 py-2">
            <div>
              <p className="text-sm font-medium text-ink">{item.type}</p>
              <p className="text-xs text-ink-secondary">
                {item.context} · {item.channel} · {item.time}
              </p>
            </div>
            <StatusPill status={item.status} />
          </div>
        )

        return (
          <li key={item.id} className="border-b border-border last:border-0">
            {item.href ? (
              <Link to={item.href} className="block hover:bg-canvas-tint">
                {content}
              </Link>
            ) : (
              content
            )}
          </li>
        )
      })}
    </ul>
  )
}
