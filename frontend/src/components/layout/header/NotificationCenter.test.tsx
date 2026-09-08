import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { notificationService } from '@/services/notificationService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { NotificationCenter } from './NotificationCenter'

describe('NotificationCenter', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('counts unread notifications from the service', async () => {
    renderWithProviders(<NotificationCenter />)
    expect(
      await screen.findByRole('button', { name: 'Notifications, 3 unread' }),
    ).toBeInTheDocument()
  })

  it('reports no unread when everything has been read', async () => {
    for (const notification of store.notifications) notification.read = true

    renderWithProviders(<NotificationCenter />)
    expect(
      await screen.findByRole('button', { name: 'Notifications, no unread' }),
    ).toBeInTheDocument()
  })

  it('lists notifications with a relative time', async () => {
    const user = userEvent.setup()
    renderWithProviders(<NotificationCenter />)

    await user.click(await screen.findByRole('button', { name: /notifications/i }))

    expect(
      await screen.findByText('Scheduling connection needs attention'),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/ago$|^just now$/).length).toBeGreaterThan(0)
  })

  it('marks one notification read when it is opened', async () => {
    const user = userEvent.setup()
    renderWithProviders(<NotificationCenter />)

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    await user.click(
      await screen.findByRole('link', { name: /scheduling connection needs attention/i }),
    )

    await waitFor(() => {
      expect(store.notifications.find((item) => item.id === 'ntf_0001')?.read).toBe(true)
    })
  })

  it('marks everything read from the panel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<NotificationCenter />)

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    await user.click(await screen.findByRole('button', { name: 'Mark all as read' }))

    expect(
      await screen.findByRole('button', { name: 'Notifications, no unread' }),
    ).toBeInTheDocument()
  })

  it('shows an empty state when there is nothing to report', async () => {
    store.notifications.length = 0
    const user = userEvent.setup()
    renderWithProviders(<NotificationCenter />)

    await user.click(await screen.findByRole('button', { name: /notifications/i }))

    expect(await screen.findByText('You are all caught up')).toBeInTheDocument()
  })

  it('does not re-mark an already-read notification when it is opened', async () => {
    const markReadSpy = vi.spyOn(notificationService, 'markRead')
    const user = userEvent.setup()
    renderWithProviders(<NotificationCenter />)

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    await user.click(
      await screen.findByRole('link', { name: /business hours are incomplete/i }),
    )

    await waitFor(() => {
      expect(store.notifications.find((item) => item.id === 'ntf_0004')?.read).toBe(true)
    })
    expect(markReadSpy).not.toHaveBeenCalled()
  })

  it('renders a distinct icon per notification kind', async () => {
    const user = userEvent.setup()
    renderWithProviders(<NotificationCenter />)

    await user.click(await screen.findByRole('button', { name: /notifications/i }))

    expect(await screen.findByTestId('notification-icon-integration_failure')).toBeInTheDocument()
    expect(screen.getByTestId('notification-icon-escalation')).toBeInTheDocument()
    expect(screen.getByTestId('notification-icon-configuration_issue')).toBeInTheDocument()
  })
})
