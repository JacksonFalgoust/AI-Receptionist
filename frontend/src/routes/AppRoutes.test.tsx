import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AuthProvider } from '@/features/auth/AuthProvider'
import { MOCK_PASSWORD } from '@/mocks/session'

import { AppRoutes } from './AppRoutes'

function renderApp(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
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
})
