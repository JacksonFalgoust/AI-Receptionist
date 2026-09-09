import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { RecentActivityCard } from './RecentActivityCard'

describe('RecentActivityCard', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('shows what Concierge just did, with customer, channel, and time (US-2.4)', async () => {
    renderWithProviders(<RecentActivityCard />)

    expect(await screen.findByText('Appointment booked')).toBeInTheDocument()
    expect(screen.getByText('Alex Morgan · Voice · 4 minutes ago')).toBeInTheDocument()
  })

  it('states each outcome in words, so status is never carried by colour alone', async () => {
    renderWithProviders(<RecentActivityCard />)

    expect((await screen.findByText('Escalated to team')).closest('li')).toHaveTextContent(
      'Escalated',
    )
    expect(screen.getByText('Scheduling lookup failed').closest('li')).toHaveTextContent('Error')
    expect(screen.getByText('Callback requested').closest('li')).toHaveTextContent('Pending')
  })

  it('falls back to the system that acted when an item has no customer', async () => {
    store.activityEvents = [
      {
        id: 'act_9001',
        organizationId: store.activityEvents[0].organizationId,
        at: new Date().toISOString(),
        title: 'Nightly availability sync',
        channel: 'voice',
        system: 'Scheduling',
        status: 'success',
      },
    ]
    renderWithProviders(<RecentActivityCard />)

    expect(await screen.findByText('Scheduling · Voice · just now')).toBeInTheDocument()
  })

  it('links an item through to its conversation', async () => {
    renderWithProviders(<RecentActivityCard />)

    expect((await screen.findByText('Appointment booked')).closest('a')).toHaveAttribute(
      'href',
      '/conversations/conv_0001',
    )
  })

  it('links to the full conversations list', () => {
    renderWithProviders(<RecentActivityCard />)

    expect(screen.getByRole('link', { name: 'View conversations' })).toHaveAttribute(
      'href',
      '/conversations',
    )
  })

  it('shows an empty state when nothing has happened yet', async () => {
    store.activityEvents.length = 0
    renderWithProviders(<RecentActivityCard />)

    expect(await screen.findByText('No recent activity')).toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })
})
