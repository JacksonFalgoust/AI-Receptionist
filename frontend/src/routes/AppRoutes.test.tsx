import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ConfirmDialogProvider } from '@/components/ui/ConfirmDialog'
import { ToastProvider } from '@/components/ui/ToastProvider'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { MOCK_PASSWORD } from '@/mocks/session'
import { seedSession } from '@/test/renderWithProviders'

import { AppRoutes } from './AppRoutes'

function renderApp(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  // Mirrors App.tsx's provider tree: the knowledge editor route now reaches
  // for both useToast and useConfirm.
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <ToastProvider>
          <ConfirmDialogProvider>
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          </ConfirmDialogProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('application routing', () => {
  it('redirects an unauthenticated visitor to the login screen', async () => {
    renderApp('/overview')

    expect(
      await screen.findByRole('heading', { name: /GuideAnts Concierge/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Manage your AI Concierge')).toBeInTheDocument()
  })

  it('signs a user in and lands them on Overview', async () => {
    const user = userEvent.setup()
    renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'owner@horizonpartners.com')
    await user.type(screen.getByLabelText('Password'), MOCK_PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    // Shell rendered too, not just the page.
    expect(screen.getByLabelText(/Organization: Horizon Partners/)).toBeInTheDocument()
  })

  it('rejects a wrong password with human-readable copy, not a status code', async () => {
    const user = userEvent.setup()
    renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'owner@horizonpartners.com')
    await user.type(screen.getByLabelText('Password'), 'not-the-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /email and password combination is not recognised/i,
    )
  })

  it('hides admin-only routes from roles that lack the permission', async () => {
    const user = userEvent.setup()
    renderApp('/login')

    // The mock signs in as the role named in the email local-part.
    await user.type(await screen.findByLabelText('Email'), 'analyst@horizonpartners.com')
    await user.type(screen.getByLabelText('Password'), MOCK_PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await screen.findByRole('heading', { name: 'Overview' })
    expect(screen.queryByRole('link', { name: 'Users & Roles' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Billing' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analytics' })).toBeInTheDocument()
  })

  it('resolves the knowledge editor routes C1 links to', async () => {
    // US-5.1's add actions and row Edit links point at these two routes. They
    // render US-5.2's editor once C2 lands; until then a stub, so the links
    // are real navigation rather than dead buttons.
    seedSession()

    renderApp('/concierge/knowledge/new')
    expect(await screen.findByRole('heading', { name: 'Add knowledge' })).toBeInTheDocument()

    renderApp('/concierge/knowledge/kn_0001')
    expect(await screen.findByRole('heading', { name: 'Edit knowledge' })).toBeInTheDocument()
  })

  it('guards the knowledge editor with the same permission as the library', async () => {
    seedSession('analyst@horizonpartners.example.com')

    renderApp('/concierge/knowledge/new')

    // An analyst has no manage:knowledge — the guard must send them away
    // rather than render the editor.
    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Add knowledge' })).not.toBeInTheDocument()
  })
})
