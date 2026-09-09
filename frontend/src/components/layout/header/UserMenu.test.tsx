import { beforeEach, describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore } from '@/mocks/store'
import { SESSION_STORAGE_KEY } from '@/services/config'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { UserMenu } from './UserMenu'

describe('UserMenu', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('labels the trigger with the account holder and shows their initials', () => {
    renderWithProviders(<UserMenu />)
    const trigger = screen.getByRole('button', { name: 'Account for Jordan Lee' })

    expect(trigger).toBeInTheDocument()
    expect(trigger).toHaveTextContent('JL')
  })

  it('shows the name and email in the panel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserMenu />)

    await user.click(screen.getByRole('button', { name: 'Account for Jordan Lee' }))

    expect(screen.getByText('Jordan Lee')).toBeInTheDocument()
    expect(screen.getByText('owner@horizonpartners.example.com')).toBeInTheDocument()
  })

  it('renders the not-yet-available entries as disabled', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserMenu />)

    await user.click(screen.getByRole('button', { name: 'Account for Jordan Lee' }))

    for (const label of ['Profile', 'Organization settings', 'Account settings']) {
      expect(screen.getByRole('menuitem', { name: label })).toBeDisabled()
    }
  })

  it('signs the user out', async () => {
    const user = userEvent.setup()
    renderWithProviders(<UserMenu />)

    await user.click(screen.getByRole('button', { name: 'Account for Jordan Lee' }))
    await user.click(screen.getByRole('menuitem', { name: 'Log out' }))

    await waitFor(() => {
      expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull()
    })
  })
})
