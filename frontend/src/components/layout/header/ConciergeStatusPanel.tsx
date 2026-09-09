import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Dropdown } from '@/components/ui/Dropdown'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { StatusPill } from '@/components/ui/StatusPill'
import { cn } from '@/lib/cn'
import { relativeTime } from '@/lib/formatDate'
import { statusTone, TONE_CLASSES } from '@/lib/statusTone'
import { paths } from '@/routes/paths'
import { conciergeService } from '@/services/conciergeService'
import type { Channel } from '@/types'

const CHANNEL_LABELS: Record<Channel, string> = {
  voice: 'Voice',
  sms: 'SMS',
  web: 'Web',
  other: 'Other',
}

/**
 * PRD §6.2: clicking the header status opens a panel showing the current
 * state, active channels, recent system issues, and the last configuration
 * change. US-2.3's Overview card reads the same service.
 */
export function ConciergeStatusPanel() {
  const query = useQuery({
    queryKey: ['concierge', 'status'],
    queryFn: () => conciergeService.getStatus(),
  })

  const tone = query.data ? statusTone(query.data.state) : undefined

  return (
    <Dropdown
      role="dialog"
      label="Concierge status"
      trigger={
        <button
          type="button"
          aria-label={`Concierge status: ${tone?.label ?? 'loading'}`}
          className={cn(
            'hidden items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold sm:flex',
            TONE_CLASSES[tone?.tone ?? 'muted'],
          )}
        >
          {/* PRD §31: the dot is decoration; the label carries the status. */}
          <span className="size-2 rounded-full bg-current" aria-hidden="true" />
          Concierge {tone?.label ?? '…'}
        </button>
      }
    >
      <div className="w-72 p-2">
        <QueryBoundary query={query} skeletonRows={4}>
          {(status) => {
            const issues = status.connectedSystems.filter(
              (system) => system.health !== 'ok',
            )

            return (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">Concierge</span>
                  <StatusPill status={status.state} />
                </div>

                <div>
                  <p className="mb-1 text-xs font-semibold text-ink-muted">Channels</p>
                  <ul className="space-y-1">
                    {status.channels.map((channel) => (
                      <li
                        key={channel.channel}
                        className="flex items-center justify-between gap-2 text-sm"
                      >
                        <span className="text-ink">{CHANNEL_LABELS[channel.channel]}</span>
                        <StatusPill status={channel.health} />
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <p className="mb-1 text-xs font-semibold text-ink-muted">Recent issues</p>
                  {issues.length ? (
                    <ul className="space-y-1">
                      {issues.map((system) => (
                        <li
                          key={system.id}
                          className="flex items-center justify-between gap-2 text-sm"
                        >
                          <span className="text-ink">{system.name}</span>
                          <StatusPill status={system.health} />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-ink-secondary">
                      No issues reported in connected systems.
                    </p>
                  )}
                </div>

                <p className="text-xs text-ink-muted">
                  Last configuration change{' '}
                  {status.lastConfigurationChangeAt
                    ? relativeTime(status.lastConfigurationChangeAt)
                    : 'not recorded'}
                </p>

                <Link
                  to={paths.configuration}
                  className="block border-t border-border pt-2 text-sm font-semibold text-brand-ink hover:underline"
                >
                  Open Configuration
                </Link>
              </div>
            )
          }}
        </QueryBoundary>
      </div>
    </Dropdown>
  )
}
