import type { ReactNode } from 'react'

import { isAppError } from '@/services/errors'

import { EmptyState } from './EmptyState'
import type { EmptyStateProps } from './EmptyState'
import { ErrorState } from './ErrorState'
import { Skeleton } from './Skeleton'
import type { SkeletonVariant } from './Skeleton'

/**
 * Structural subset of TanStack's `UseQueryResult`. A real query result
 * satisfies it, and so does a plain object — which keeps tests free of a
 * `QueryClientProvider`.
 */
export interface QueryBoundaryResult<T> {
  data: T | undefined
  error: unknown
  isPending: boolean
  isError: boolean
  refetch?: () => unknown
}

export interface QueryBoundaryProps<T> {
  query: QueryBoundaryResult<T>
  /** Receives non-nullable data — success markup cannot be written against undefined. */
  children: (data: T) => ReactNode
  skeleton?: SkeletonVariant
  skeletonRows?: number
  isEmpty?: (data: T) => boolean
  empty?: EmptyStateProps
}

/**
 * PRD §39: every API-driven component supports Loading, Success, Empty, Error
 * and Unauthorized. This is the single place those five are decided — nothing
 * in Phases B–E hand-rolls loading or error markup (US-0.3).
 */
export function QueryBoundary<T>({
  query,
  children,
  skeleton = 'text',
  skeletonRows,
  isEmpty,
  empty,
}: QueryBoundaryProps<T>) {
  if (query.isPending) {
    return <Skeleton variant={skeleton} rows={skeletonRows} />
  }

  if (query.isError) {
    // The cache-level handler has already dropped the session and a redirect is
    // one render away. An error card here would flash "session expired" on the
    // page being left as well as on the login screen being arrived at.
    if (isAppError(query.error) && query.error.kind === 'unauthorized') {
      return null
    }
    return <ErrorState error={query.error} onRetry={query.refetch} />
  }

  if (query.data === undefined) {
    return null
  }

  if (isEmpty?.(query.data)) {
    return <EmptyState {...(empty ?? { title: 'Nothing to show yet' })} />
  }

  return <>{children(query.data)}</>
}
