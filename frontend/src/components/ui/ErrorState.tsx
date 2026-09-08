import { Link } from 'react-router-dom'

import { toAppError } from '@/services/errors'

import { Button, buttonClasses } from './Button'

export interface ErrorStateProps {
  error: unknown
  /** Bound to any action carrying `retry: true`. Omit and no retry renders. */
  onRetry?: () => void
}

/**
 * PRD §27: errors are human-readable, with actions the user can actually take.
 * Sibling to `EmptyState` — every async view routes failures through here so
 * error markup is never rewritten per screen.
 */
export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const appError = toAppError(error)

  return (
    <div role="alert" className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <p className="text-sm font-semibold text-ink">{appError.title}</p>
      <p className="max-w-md text-sm text-ink-secondary">{appError.description}</p>

      {appError.actions.length ? (
        <div className="mt-2 flex flex-wrap justify-center gap-2">
          {appError.actions.map((action) => {
            if (action.retry) {
              return onRetry ? (
                <Button key={action.label} size="sm" onClick={onRetry}>
                  {action.label}
                </Button>
              ) : null
            }
            if (action.href) {
              return (
                <Link
                  key={action.label}
                  to={action.href}
                  className={buttonClasses('ghost', 'sm')}
                >
                  {action.label}
                </Link>
              )
            }
            return null
          })}
        </div>
      ) : null}
    </div>
  )
}
