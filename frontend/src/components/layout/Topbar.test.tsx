import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { Topbar } from './Topbar'

describe('Topbar', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('renders all four header controls', async () => {
    renderWithProviders(<Topbar onOpenNav={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'Organization: Horizon Partners' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Concierge status: Active' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /notifications/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Account for Jordan Lee' })).toBeInTheDocument()
  })

  it('opens the test drawer instead of navigating', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Topbar onOpenNav={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /test concierge/i }))
    expect(await screen.findByRole('dialog', { name: 'Test Concierge' })).toBeInTheDocument()
  })

  it('hides Test Concierge for a role without use:test', () => {
    seedSession('agent@horizonpartners.example.com')
    renderWithProviders(<Topbar onOpenNav={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /test concierge/i })).not.toBeInTheDocument()
  })

  it('opens the mobile navigation', async () => {
    const user = userEvent.setup()
    const onOpenNav = vi.fn()
    renderWithProviders(<Topbar onOpenNav={onOpenNav} />)

    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(onOpenNav).toHaveBeenCalledOnce()
  })

  it('derives the unread count from the service rather than hard-coding it', async () => {
    // Topbar previously rendered a literal `3`. Changing the data must change
    // the label — that is the only assertion that can catch a regression here.
    for (const notification of store.notifications) notification.read = true

    renderWithProviders(<Topbar onOpenNav={vi.fn()} />)

    expect(
      await screen.findByRole('button', { name: 'Notifications, no unread' }),
    ).toBeInTheDocument()
  })
})
