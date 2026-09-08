/**
 * PRD §27: users must never see `API_ERROR_451`. Every service failure is
 * normalised into an `AppError` carrying human-readable copy plus the next
 * steps a user can actually take, so error UI is structural rather than
 * reinvented on each screen.
 */

export type AppErrorKind =
  | 'network'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'validation'
  | 'server'
  | 'unknown'

export interface AppErrorAction {
  label: string
  /** In-app route to navigate to, e.g. `/integrations`. */
  href?: string
  /** Marks the action as "re-run the failed request". */
  retry?: boolean
}

export class AppError extends Error {
  readonly kind: AppErrorKind
  /** Short headline, e.g. "Reservation system unavailable". */
  readonly title: string
  /** One or two sentences explaining what happened, in business language. */
  readonly description: string
  readonly actions: AppErrorAction[]
  /** Field-level messages for form submissions, keyed by field name. */
  readonly fieldErrors?: Record<string, string>

  constructor(params: {
    kind: AppErrorKind
    title: string
    description: string
    actions?: AppErrorAction[]
    fieldErrors?: Record<string, string>
  }) {
    super(`${params.title}: ${params.description}`)
    this.name = 'AppError'
    this.kind = params.kind
    this.title = params.title
    this.description = params.description
    this.actions = params.actions ?? []
    this.fieldErrors = params.fieldErrors
  }
}

export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError
}

/** Fallback for anything that reaches the UI without already being an AppError. */
export function toAppError(error: unknown): AppError {
  if (isAppError(error)) return error

  return new AppError({
    kind: 'unknown',
    title: 'Something went wrong',
    description:
      'The request could not be completed. Try again, and contact support if the problem continues.',
    actions: [{ label: 'Retry', retry: true }],
  })
}
