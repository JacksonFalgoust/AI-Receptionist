import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button, buttonClasses } from '@/components/ui/Button'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { StatusPill } from '@/components/ui/StatusPill'
import { useConfirm } from '@/components/ui/useConfirm'
import { useToast } from '@/components/ui/ToastProvider'
import { CHANNEL_LABELS } from '@/lib/channelLabels'
import { relativeTime } from '@/lib/formatDate'
import { paths } from '@/routes/paths'
import { conciergeService } from '@/services/conciergeService'
import { toAppError } from '@/services/errors'
import type { Channel, ConciergeState, ConciergeStatus } from '@/types'

/**
 * Deliberately the same literal the header badge uses, so one fetch feeds both
 * and pausing here updates the badge in the same tick. Kept inline rather than
 * shared: query keys stay plain arrays until something forces a key factory.
 */
const CONCIERGE_STATUS_KEY = ['concierge', 'status']

/**
 * US-2.3: Voice and SMS only. Enforced here rather than left to whatever the
 * service returns — the Conversations list still shows Web (US-3.1), so the
 * constraint belongs to this card, not to the data.
 */
const OVERVIEW_CHANNELS: Channel[] = ['voice', 'sms']

/** The pill carries the short status; the hero says what it means for callers. */
const STATE_SENTENCE: Record<ConciergeState, string> = {
  active: 'Active and responding',
  paused: 'Paused — callers are not being answered',
  setup_required: 'Setup required before Concierge can answer',
  maintenance: 'Under maintenance',
  connection_issue: 'Running with a connection issue',
}

/**
 * US-2.3: operational state, channels, connected systems, and the actions an
 * administrator needs when something looks wrong.
 */
export function ConciergeStatusCard() {
  const query = useQuery({
    queryKey: CONCIERGE_STATUS_KEY,
    queryFn: () => conciergeService.getStatus(),
  })

  return (
    <Panel>
      <PanelHeader
        title="Concierge Status"
        action={
          <Link
            to={paths.configuration}
            className="text-sm font-semibold text-brand-ink hover:underline"
          >
            View configuration
          </Link>
        }
      />
      <div className="p-4">
        <QueryBoundary query={query} skeletonRows={5}>
          {(status) => <StatusCardBody status={status} />}
        </QueryBoundary>
      </div>
    </Panel>
  )
}

function StatusCardBody({ status }: { status: ConciergeStatus }) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const toast = useToast()

  const isPaused = status.state === 'paused'

  const toggle = useMutation({
    mutationFn: () => (isPaused ? conciergeService.resume() : conciergeService.pause()),
    onSuccess: (next) => {
      // The response is the whole status, so seed the cache rather than
      // invalidating — every consumer of this key updates without a refetch.
      queryClient.setQueryData(CONCIERGE_STATUS_KEY, next)
      toast.show(
        isPaused ? 'Concierge resumed. Callers are being answered.' : 'Concierge paused.',
        { tone: 'success' },
      )
    },
    onError: (error) => {
      toast.show(toAppError(error).description, { tone: 'danger' })
    },
  })

  // Pausing stops answering real callers; resuming only restores service.
  async function onToggle() {
    if (!isPaused) {
      const confirmed = await confirm({
        title: 'Pause Concierge?',
        description:
          'Concierge stops answering calls and messages until you resume it. Callers will not reach it in the meantime.',
        confirmLabel: 'Pause Concierge',
        tone: 'danger',
      })
      if (!confirmed) return
    }
    toggle.mutate()
  }

  const channels = OVERVIEW_CHANNELS.map((channel) =>
    status.channels.find((item) => item.channel === channel),
  ).filter((item) => item !== undefined)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{STATE_SENTENCE[status.state]}</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            Last configuration change{' '}
            {status.lastConfigurationChangeAt
              ? relativeTime(status.lastConfigurationChangeAt)
              : 'not recorded'}
          </p>
        </div>
        <StatusPill status={status.state} />
      </div>

      <div role="group" aria-label="Channels">
        <ul className="divide-y divide-border rounded-sm border border-border">
          {channels.map((channel) => (
            <li
              key={channel.channel}
              className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
            >
              <span className="text-ink">{CHANNEL_LABELS[channel.channel]}</span>
              <StatusPill status={channel.enabled ? channel.health : 'disabled'} />
            </li>
          ))}
        </ul>
      </div>

      <div role="group" aria-label="Connected systems">
        <p className="mb-1.5 text-xs font-semibold text-ink-muted">Connected systems</p>
        <ul className="space-y-1">
          {status.connectedSystems.map((system) => (
            <li key={system.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="text-ink">
                {system.name}
                {system.lastSyncAt ? (
                  <span className="text-ink-muted"> — synced {relativeTime(system.lastSyncAt)}</span>
                ) : null}
              </span>
              <StatusPill status={system.health} />
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        {/* E3 replaces this link with the global test drawer. */}
        <Link to={paths.test} className={buttonClasses('primary', 'sm')}>
          Test Concierge
        </Link>
        <Button variant="ghost" size="sm" onClick={onToggle} disabled={toggle.isPending}>
          {isPaused ? 'Resume Concierge' : 'Pause Concierge'}
        </Button>
      </div>
    </div>
  )
}
