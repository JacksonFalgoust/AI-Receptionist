import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Button, buttonClasses } from './Button'

/**
 * Exactly one of `href` and `onClick`. A CTA that navigates must be a real
 * link — a button cannot be opened in a new tab and does not announce itself
 * as a destination — while one that acts in place must be a button. The
 * `never` arms make a CTA that does nothing, or one whose handler would be
 * silently discarded in favour of its href, a compile error.
 */
export type EmptyStateAction =
  | { label: string; href: string; onClick?: never }
  | { label: string; onClick: () => void; href?: never }

export interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: EmptyStateAction
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      {icon}
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description ? <p className="text-sm text-ink-secondary">{description}</p> : null}
      {action?.href !== undefined ? (
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
