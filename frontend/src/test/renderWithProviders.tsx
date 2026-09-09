import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog'
import { ToastProvider } from '@/components/ui/ToastProvider'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { buildMockSessionUser } from '@/mocks/session'
import { SESSION_STORAGE_KEY } from '@/services/config'

/**
 * Test harness for components that need a query client, a router, a signed-in
 * user, toasts, and confirmations. It mirrors the provider tree in `App.tsx`,
 * so a component that works under test works mounted for real —
 * `useToast()` and `useConfirm()` both throw without their providers.
 *
 * `src/test/setup.ts` clears localStorage after each test, so a session seeded
 * here never leaks into the next case.
 */

export function seedSession(email = 'owner@horizonpartners.example.com'): void {
  localStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify({
      token: 'test-token',
      user: buildMockSessionUser(email),
      expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
    }),
  )
}

export interface RenderWithProvidersOptions {
  route?: string
}

export function renderWithProviders(
  ui: ReactElement,
  { route = '/' }: RenderWithProvidersOptions = {},
) {
  // Retries would turn a deliberate error case into a multi-second timeout.
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <ToastProvider>
            <ConfirmDialogProvider>
              <AuthProvider>{children}</AuthProvider>
            </ConfirmDialogProvider>
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper }) }
}
