import { describe, expect, it } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'

import { notifySessionExpired } from '@/lib/sessionExpiry'
import { buildMockSessionUser, MOCK_PASSWORD } from '@/mocks/session'
import { SESSION_STORAGE_KEY } from '@/services/config'

import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'

function seedStoredSession() {
  localStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify({
      token: 'test-token',
      user: buildMockSessionUser('owner@horizonpartners.com'),
      expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
    }),
  )
}

function Probe() {
  const { user, sessionExpired, signIn } = useAuth()
  return (
    <div>
      <span data-testid="user">{user?.email ?? 'signed-out'}</span>
      <span data-testid="expired">{String(sessionExpired)}</span>
      <button type="button" onClick={() => void signIn('owner@horizonpartners.com', MOCK_PASSWORD)}>
        Sign in
      </button>
    </div>
  )
}

describe('AuthProvider session expiry', () => {
  it('starts with sessionExpired false', () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    expect(screen.getByTestId('expired')).toHaveTextContent('false')
  })

  it('clears the session and flags expiry when notified', async () => {
    seedStoredSession()
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    expect(screen.getByTestId('user')).toHaveTextContent('owner@horizonpartners.com')

    await act(async () => {
      notifySessionExpired()
    })

    expect(screen.getByTestId('user')).toHaveTextContent('signed-out')
    expect(screen.getByTestId('expired')).toHaveTextContent('true')
  })

  it('resets the expiry flag on a successful sign-in', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await act(async () => {
      notifySessionExpired()
    })
    expect(screen.getByTestId('expired')).toHaveTextContent('true')

    act(() => {
      screen.getByRole('button', { name: 'Sign in' }).click()
    })

    // The mock authService applies an artificial network delay, so the state
    // update lands after a real macrotask tick rather than within `act`.
    await waitFor(() => {
      expect(screen.getByTestId('expired')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('user')).toHaveTextContent('owner@horizonpartners.com')
  })
})
