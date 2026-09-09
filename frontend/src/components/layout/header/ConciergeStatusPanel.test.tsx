import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ConciergeStatusPanel } from './ConciergeStatusPanel'

async function openPanel() {
  const user = userEvent.setup()
  renderWithProviders(<ConciergeStatusPanel />)
  await user.click(await screen.findByRole('button', { name: /concierge status/i }))
  return user
}

describe('ConciergeStatusPanel', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('labels the trigger with the current state, not colour alone (PRD §31)', async () => {
    renderWithProviders(<ConciergeStatusPanel />)
    expect(
      await screen.findByRole('button', { name: 'Concierge status: Active' }),
    ).toBeInTheDocument()
  })

  it('reflects a paused Concierge', async () => {
    store.conciergeStatus.state = 'paused'
    renderWithProviders(<ConciergeStatusPanel />)
    expect(
      await screen.findByRole('button', { name: 'Concierge status: Paused' }),
    ).toBeInTheDocument()
  })

  it('shows Voice and SMS channels with their health', async () => {
    await openPanel()

    expect(await screen.findByText('Voice')).toBeInTheDocument()
    expect(screen.getByText('SMS')).toBeInTheDocument()
    expect(screen.queryByText('Web')).not.toBeInTheDocument()
  })

  it('lists systems that need attention as recent issues', async () => {
    await openPanel()

    expect(await screen.findByText('Scheduling')).toBeInTheDocument()
    // Healthy systems are not noise in an issues list.
    expect(screen.queryByText('Payments')).not.toBeInTheDocument()
  })

  it('says when configuration last changed', async () => {
    await openPanel()
    expect(await screen.findByText(/last configuration change/i)).toBeInTheDocument()
  })

  it('links to Configuration', async () => {
    await openPanel()
    expect(await screen.findByRole('link', { name: /configuration/i })).toHaveAttribute(
      'href',
      '/concierge/configuration',
    )
  })
})
