import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { RecentEscalationsCard } from './RecentEscalationsCard'

/** The row a given customer's escalation is rendered in. */
function rowFor(customerName: string): HTMLElement {
  const row = screen.getByText(customerName).closest('tr')
  if (!row) throw new Error(`No row found for ${customerName}`)
  return row
}

describe('RecentEscalationsCard', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('shows the five columns US-2.5 asks for', async () => {
    renderWithProviders(<RecentEscalationsCard />)

    await screen.findByText('Dana Wu')
    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['Customer', 'Time', 'Reason', 'Assigned', 'Status'])
  })

  it('names who is handling each escalation, or says plainly that nobody is', async () => {
    renderWithProviders(<RecentEscalationsCard />)

    expect(await screen.findByText('Dana Wu')).toBeInTheDocument()
    // conv_0002's assignedEmployee is Taylor Brooks; the escalation row must
    // agree, not contradict the Conversations list for the same conversation.
    expect(rowFor('Dana Wu')).toHaveTextContent('Taylor Brooks')
    expect(rowFor('Marcus Bell')).toHaveTextContent('Priya Shah')
    // Alex Morgan's escalation is deliberately left unassigned so the
    // "Unassigned" rendering branch keeps coverage.
    expect(rowFor('Alex Morgan')).toHaveTextContent('Unassigned')
  })

  it('states every escalation status in words, across all four values', async () => {
    renderWithProviders(<RecentEscalationsCard />)

    await screen.findByText('Dana Wu')
    expect(rowFor('Dana Wu')).toHaveTextContent('New')
    expect(rowFor('Marcus Bell')).toHaveTextContent('Assigned')
    expect(rowFor('Nate Fischer')).toHaveTextContent('In progress')
    expect(rowFor('Ibrahim Khan')).toHaveTextContent('Resolved')
  })

  it('links a customer through to the conversation that escalated', async () => {
    renderWithProviders(<RecentEscalationsCard />)

    expect(await screen.findByRole('link', { name: 'Dana Wu' })).toHaveAttribute(
      'href',
      '/conversations/conv_0002',
    )
  })

  it('leaves the customer as plain text when no conversation is recorded', async () => {
    store.escalations = [
      {
        ...store.escalations[0],
        id: 'esc_9001',
        customerName: 'Priya Shah',
        conversationId: undefined,
      },
    ]
    renderWithProviders(<RecentEscalationsCard />)

    expect(await screen.findByText('Priya Shah')).toBeInTheDocument()
    expect(within(rowFor('Priya Shah')).queryByRole('link')).not.toBeInTheDocument()
  })

  it('links to escalation and routing management', () => {
    renderWithProviders(<RecentEscalationsCard />)

    expect(screen.getByRole('link', { name: 'Manage routing' })).toHaveAttribute('href', '/routing')
  })

  it('shows an empty state when nobody is needed', async () => {
    store.escalations.length = 0
    renderWithProviders(<RecentEscalationsCard />)

    expect(await screen.findByText('No recent escalations')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('honours the page date scope, hiding escalations outside the window', async () => {
    const DAY = 24 * 60 * 60 * 1000
    const template = store.escalations[0]
    store.escalations = [
      { ...template, id: 'esc_now', customerName: 'Nadia Rahman', createdAt: new Date().toISOString() },
      {
        ...template,
        id: 'esc_old',
        customerName: 'Owen Pritchard',
        createdAt: new Date(Date.now() - 14 * DAY).toISOString(),
      },
    ]
    renderWithProviders(<RecentEscalationsCard range={{ preset: 'today' }} />)

    expect(await screen.findByText('Nadia Rahman')).toBeInTheDocument()
    expect(screen.queryByText('Owen Pritchard')).not.toBeInTheDocument()
  })
})
