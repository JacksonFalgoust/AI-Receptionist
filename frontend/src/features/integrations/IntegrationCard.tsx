import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { integrationCategoryLabel } from '@/lib/integrationLabels'
import { relativeTime } from '@/lib/formatDate'
import type { Integration } from '@/types'

export interface IntegrationCardProps {
  integration: Integration
}

/**
 * US-9.1: pure display, one card per catalog entry. Unlike `FeatureCard`,
 * this owns no query or mutation — Connect/Repair/Disconnect are D2's.
 */
export function IntegrationCard({ integration }: IntegrationCardProps) {
  return (
    <Panel role="group" aria-label={integration.name} className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{integration.name}</h3>
          <p className="mt-0.5 text-sm text-ink-secondary">
            {integrationCategoryLabel(integration.category)}
          </p>
        </div>
        <StatusPill status={integration.status} />
      </div>
      <div className="space-y-1 text-sm text-ink-secondary">
        <p>
          {integration.lastActivityAt
            ? `Last activity: ${relativeTime(integration.lastActivityAt)}`
            : 'No activity yet'}
        </p>
        {integration.connectedAccount ? <p>Account: {integration.connectedAccount}</p> : null}
        <p>
          {integration.features.length > 0
            ? `Features: ${integration.features.join(', ')}`
            : 'Not used by any feature yet'}
        </p>
      </div>
    </Panel>
  )
}
