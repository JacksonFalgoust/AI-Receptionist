import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'

import { resetStore } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { OverviewPage } from './OverviewPage'

describe('OverviewPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', () => {
    renderWithProviders(<OverviewPage />)

    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
  })

  it('shows the key metrics row', async () => {
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText('Conversations Today')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Key metrics' })).toBeInTheDocument()
  })

  it('shows the Concierge status card', async () => {
    renderWithProviders(<OverviewPage />)

    expect(screen.getByRole('heading', { name: 'Concierge Status' })).toBeInTheDocument()
    expect(await screen.findByText('Active and responding')).toBeInTheDocument()
  })

  it('pairs the status card with the recent activity feed', async () => {
    renderWithProviders(<OverviewPage />)

    const paired = screen.getByRole('region', { name: 'Status and recent activity' })
    expect(within(paired).getByRole('heading', { name: 'Concierge Status' })).toBeInTheDocument()
    expect(within(paired).getByRole('heading', { name: 'Recent Activity' })).toBeInTheDocument()
    expect(await within(paired).findByText('Appointment booked')).toBeInTheDocument()
  })
})
