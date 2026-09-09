import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Button, buttonClasses } from './Button'

export interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  /**
   * `href` for an action that navigates — it must be a real link so it can be
   * opened in a new tab and read as a destination — and `onClick` for one that
   * acts in place. Supply one or the other.
   */
  action?: { label: string; href?: string; onClick?: () => void }
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      {icon}
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description ? <p className="text-sm text-ink-secondary">{description}</p> : null}
      {action?.href ? (
        <Link to={action.href} className={buttonClasses('primary', 'sm', 'mt-2')}>
          {action.label}
        </Link>
      ) : action ? (
        <Button size="sm" onClick={action.onClick} className="mt-2">
          {action.label}
        </Button>
      ) : null}
    </div>
  )
}
