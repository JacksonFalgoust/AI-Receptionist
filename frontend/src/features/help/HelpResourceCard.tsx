import { Link } from 'react-router-dom'

import { buttonClasses } from '@/components/ui/Button'
import { Panel } from '@/components/ui/Panel'
import { useAuth } from '@/features/auth/useAuth'
import { can } from '@/lib/permissions'

import type { HelpResource } from './helpResources'

export interface HelpResourceCardProps {
  resource: HelpResource
}

/**
 * US-14.1. Mirrors `FeatureCard`'s own `Panel role="group" aria-label={...}
 * className="flex h-full flex-col gap-3 p-4"` shell and heading/description
 * markup, so this grid reads as one family of cards with the rest of the
 * app. A role lacking `action.permission` sees the title and description
 * with no link — not a disabled one — the same care E3 took with `use:test`.
 */
export function HelpResourceCard({ resource }: HelpResourceCardProps) {
  const { user } = useAuth()
  const { action } = resource
  const canAct = Boolean(
    action && (!action.permission || (user && can(user.role, action.permission))),
  )

  return (
    <Panel role="group" aria-label={resource.title} className="flex h-full flex-col gap-3 p-4">
      <div>
        <h3 className="font-semibold text-ink">{resource.title}</h3>
        <p className="mt-0.5 text-sm text-ink-secondary">{resource.description}</p>
      </div>
      {canAct && action ? (
        action.href.startsWith('mailto:') ? (
          <a href={action.href} className={buttonClasses('primary', 'sm', 'mt-auto self-start')}>
            {action.label}
          </a>
        ) : (
          <Link
            to={action.href}
            className="mt-auto text-sm font-semibold text-brand-ink hover:underline"
          >
            {action.label}
          </Link>
        )
      ) : null}
    </Panel>
  )
}
