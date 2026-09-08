import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { OrganizationMenu } from './OrganizationMenu'

describe('OrganizationMenu', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('names the current organization on the trigger', () => {
    renderWithProviders(<OrganizationMenu />)
    expect(
      screen.getByRole('button', { name: 'Organization: Horizon Partners' }),
    ).toBeInTheDocument()
  })

  it('opens a panel listing organizations from the service', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OrganizationMenu />)

    await user.click(screen.getByRole('button', { name: 'Organization: Horizon Partners' }))

    expect(await screen.findByRole('dialog', { name: 'Organizations' })).toBeInTheDocument()
    expect(await screen.findByText('2 offices')).toBeInTheDocument()
  })

  it('marks the signed-in organization as current', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OrganizationMenu />)

    await user.click(screen.getByRole('button', { name: 'Organization: Horizon Partners' }))

    expect(await screen.findByText('Current organization')).toBeInTheDocument()
  })

  it('says switching is not available yet', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OrganizationMenu />)

    await user.click(screen.getByRole('button', { name: 'Organization: Horizon Partners' }))

    expect(
      await screen.findByText(/switching between organizations/i),
    ).toBeInTheDocument()
  })
})
