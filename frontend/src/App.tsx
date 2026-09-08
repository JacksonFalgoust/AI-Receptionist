import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'

import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog'
import { ToastProvider } from '@/components/ui/ToastProvider'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { AppRoutes } from '@/routes/AppRoutes'
import { isAppError } from '@/services/errors'

const queryClient = new QueryClient({
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
