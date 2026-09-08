import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/features/auth/AuthProvider'

import { LoginPage } from './LoginPage'

function renderLogin(state?: unknown) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('LoginPage session expiry notice', () => {
  it('shows the expiry message when arriving from an expired session', () => {
    renderLogin({ sessionExpired: true })
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Your session has expired. Sign in again to continue.',
    )
  })

  it('shows no notice on a direct visit', () => {
    renderLogin()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
