/**
 * US-0.4: a 401 anywhere must land the user on `/login` with a clear message.
 *
 * The `QueryClient` that detects the 401 is constructed outside the router and
 * cannot call `useNavigate` or reach auth state. This registry is the single
 * hop between the cache handler (`App.tsx`) and `AuthProvider`, which drops the
 * session and lets `ProtectedRoute`'s existing redirect do the rest.
 */

type SessionExpiredHandler = () => void

const handlers = new Set<SessionExpiredHandler>()

/** Subscribe. Returns the unsubscribe function, for use as an effect cleanup. */
export function onSessionExpired(handler: SessionExpiredHandler): () => void {
  handlers.add(handler)
  return () => {
    handlers.delete(handler)
  }
}

export function notifySessionExpired(): void {
  // Copy first: a handler is allowed to unsubscribe itself while running.
  for (const handler of [...handlers]) {
    handler()
  }
}
