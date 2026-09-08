import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { AuthProvider } from '@/features/auth/AuthProvider'
import { authService } from '@/services/authService'
import { AppError } from '@/services/errors'

import { ForgotPasswordPage } from './ForgotPasswordPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ForgotPasswordPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ForgotPasswordPage', () => {
  it('renders the default state with a link back to sign in', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: /forgot password/i })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('validates the email before calling the service', async () => {
    const user = userEvent.setup()
    const spy = vi.spyOn(authService, 'requestPasswordReset')
    renderPage()

    await user.type(screen.getByLabelText('Email'), 'not-an-email')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })

  it('replaces the form with confirmation copy that does not reveal the account', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Email'), 'owner@horizonpartners.example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(
      await screen.findByText(/if an account exists for that address/i),
    ).toBeInTheDocument()
    // The form is gone, so the same field cannot be used to probe addresses.
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toBeInTheDocument()
  })

  it('shows a processing state while the request is in flight', async () => {
    const user = userEvent.setup()
    let resolveRequest: () => void = () => {}
    vi.spyOn(authService, 'requestPasswordReset').mockReturnValue(
      new Promise<void>((resolve) => {
        resolveRequest = resolve
      }),
    )
    renderPage()

    await user.type(screen.getByLabelText('Email'), 'owner@horizonpartners.example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByRole('button', { name: 'Sending…' })).toBeDisabled()

    resolveRequest()
    await waitFor(() => {
      expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
    })
  })

  it('shows a human-readable error and keeps the form when the request fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(authService, 'requestPasswordReset').mockRejectedValue(
      new AppError({
        kind: 'network',
        title: 'Cannot reach GuideAnts Concierge',
        description: 'Check your network connection and try again.',
      }),
    )
    renderPage()

    await user.type(screen.getByLabelText('Email'), 'owner@horizonpartners.example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Check your network connection and try again.',
    )
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })
})
