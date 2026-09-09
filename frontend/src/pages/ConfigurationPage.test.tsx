import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ConfigurationPage } from './ConfigurationPage'

describe('ConfigurationPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<ConfigurationPage />)
    expect(screen.getByRole('heading', { name: 'Configuration' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByDisplayValue('Horizon Partners')).toBeInTheDocument()
  })

  it('loads behind a loading state, then shows the current business profile', async () => {
    renderWithProviders(<ConfigurationPage />)

    expect(screen.getByRole('status')).toBeInTheDocument()

    expect(await screen.findByDisplayValue('Horizon Partners')).toBeInTheDocument()
    expect(screen.getByDisplayValue('1200 Meridian Way, Suite 400')).toBeInTheDocument()
    expect(screen.getByLabelText('Time zone')).toHaveValue('America/Chicago')
  })

  it('saves a change to the draft, toasts, and does not publish it', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)

    const name = await screen.findByDisplayValue('Horizon Partners')
    await user.clear(name)
    await user.type(name, 'Meridian Partners')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    expect(store.conciergeConfiguration.businessProfile.name).toBe('Meridian Partners')
    // PRD §13.4: saving a draft must never publish it to production.
    expect(store.conciergeConfiguration.hasUnpublishedChanges).toBe(true)
  })

  it('shows a validation error and does not save when the name is cleared', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)

    const name = await screen.findByDisplayValue('Horizon Partners')
    await user.clear(name)
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Enter a business name')).toBeInTheDocument()
    expect(store.conciergeConfiguration.businessProfile.name).toBe('Horizon Partners')
  })
})
