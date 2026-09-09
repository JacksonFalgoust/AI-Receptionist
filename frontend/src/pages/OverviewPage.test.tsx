import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
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

  it('shows where humans are needed, below the status and activity pair', async () => {
    renderWithProviders(<OverviewPage />)

    expect(screen.getByRole('heading', { name: 'Recent Escalations' })).toBeInTheDocument()
    expect(await screen.findByText('Ibrahim Khan')).toBeInTheDocument()

    const paired = screen.getByRole('region', { name: 'Status and recent activity' })
    expect(
      within(paired).queryByRole('heading', { name: 'Recent Escalations' }),
    ).not.toBeInTheDocument()
  })

  it('lands on Today and offers no Export (US-2.1)', () => {
    renderWithProviders(<OverviewPage />)

    expect(screen.getByRole('radio', { name: 'Today' })).toBeChecked()
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument()
  })

  it('widening the scope brings older work into view', async () => {
    const DAY = 24 * 60 * 60 * 1000
    const template = store.activityEvents[0]
    store.activityEvents = [
      { ...template, id: 'act_now', title: 'Handled this morning', at: new Date().toISOString() },
      {
        ...template,
        id: 'act_old',
        title: 'Handled three weeks back',
        at: new Date(Date.now() - 21 * DAY).toISOString(),
      },
    ]
    const user = userEvent.setup()
    renderWithProviders(<OverviewPage />)

    expect(await screen.findByText('Handled this morning')).toBeInTheDocument()
    expect(screen.queryByText('Handled three weeks back')).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: '30 days' }))

    expect(await screen.findByText('Handled three weeks back')).toBeInTheDocument()
  })
})
