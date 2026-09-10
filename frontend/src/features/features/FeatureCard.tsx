import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Alert } from '@/components/ui/Alert'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { featureService } from '@/services/featureService'
import { toAppError } from '@/services/errors'
import type { AppError } from '@/services/errors'
import type { Feature } from '@/types'

/** Shared with `FeaturesPage`'s list query, so a card's own mutation can patch it directly. */
export const FEATURES_KEY = ['features']

export interface FeatureCardProps {
  feature: Feature
}

/**
 * US-7.1. Self-contained the way `ConciergeStatusCard` is: its own mutation,
 * its own confirm and toast, patching the shared `['features']` cache on
 * success rather than the page tracking which card is mid-action.
 */
export function FeatureCard({ feature }: FeatureCardProps) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const toast = useToast()
  const navigate = useNavigate()
  const [setupError, setSetupError] = useState<AppError | null>(null)

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => featureService.setEnabled(feature.id, enabled),
    onSuccess: (updated) => {
      setSetupError(null)
      queryClient.setQueryData<Feature[]>(FEATURES_KEY, (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)),
      )
      toast.show(updated.status === 'enabled' ? 'Feature turned on.' : 'Feature turned off.', {
        tone: 'success',
      })
    },
    onError: (error) => {
      const appError = toAppError(error)
      // US-7.1: enabling something that still needs setup routes to the next
      // step rather than just failing — anything else is an ordinary error.
      if (appError.kind === 'validation') {
        setSetupError(appError)
      } else {
        toast.show(appError.description, { tone: 'danger' })
      }
    },
  })

  async function handleChange(checked: boolean) {
    setSetupError(null)
    if (!checked && feature.highImpact) {
      const confirmed = await confirm({
        title: `Turn off ${feature.name}?`,
        description: `Concierge will no longer be able to use ${feature.name} until this is turned back on.`,
        confirmLabel: 'Turn off',
        tone: 'danger',
      })
      if (!confirmed) return
    }
    toggle.mutate(checked)
  }

  return (
    <Panel role="group" aria-label={feature.name} className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{feature.name}</h3>
          <p className="mt-0.5 text-sm text-ink-secondary">{feature.description}</p>
        </div>
        <Toggle
          label={`Enable ${feature.name}`}
          checked={feature.status === 'enabled'}
          disabled={toggle.isPending}
          onChange={(event) => handleChange(event.target.checked)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm text-ink-secondary">
        {feature.requiredIntegrationName ? <span>Requires {feature.requiredIntegrationName}</span> : null}
        <StatusPill status={feature.status} />
      </div>
      {setupError ? (
        <Alert
          tone="warning"
          title={setupError.title}
          description={setupError.description}
          actions={setupError.actions.map((action) => ({
            label: action.label,
            onClick: () => {
              if (action.href) navigate(action.href)
            },
          }))}
        />
      ) : null}
    </Panel>
  )
}
