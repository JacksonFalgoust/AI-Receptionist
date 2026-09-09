import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'

import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog'
import { ToastProvider } from '@/components/ui/ToastProvider'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { notifySessionExpired } from '@/lib/sessionExpiry'
import { AppRoutes } from '@/routes/AppRoutes'
import { isAppError } from '@/services/errors'

/**
 * US-0.4. Covering the mutation cache is the point: a 401 from a save or
 * publish never passes through a `QueryBoundary`, and without this the user
 * would be left on a dead page holding an invalid session.
 */
function handleQueryError(error: unknown): void {
  if (isAppError(error) && error.kind === 'unauthorized') {
    notifySessionExpired()
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleQueryError }),
  mutationCache: new MutationCache({ onError: handleQueryError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Retrying a permission or validation failure just delays the error UI.
        if (isAppError(error) && error.kind !== 'network' && error.kind !== 'server') {
          return false
        }
        return failureCount < 2
      },
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <ConfirmDialogProvider>
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          </ConfirmDialogProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
