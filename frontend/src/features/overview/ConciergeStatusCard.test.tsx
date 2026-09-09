import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ConciergeStatusPanel } from '@/components/layout/header/ConciergeStatusPanel'
import { resetStore, store } from '@/mocks/store'
import { conciergeService } from '@/services/conciergeService'
import { AppError } from '@/services/errors'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ConciergeStatusCard } from './ConciergeStatusCard'

/** Confirms the pending `useConfirm()` dialog by its action button. */
async function confirmDialog(user: ReturnType<typeof userEvent.setup>, label: string) {
  const dialog = await screen.findByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: label }))
}

describe('ConciergeStatusCard', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('reports the state and when configuration last changed', async () => {
    renderWithProviders(<ConciergeStatusCard />)

    expect(await screen.findByText('Active and responding')).toBeInTheDocument()
    expect(screen.getByText(/last configuration change/i)).toBeInTheDocument()
  })

  it('says so plainly when configuration has never been changed', async () => {
    delete store.conciergeStatus.lastConfigurationChangeAt
    renderWithProviders(<ConciergeStatusCard />)

    expect(await screen.findByText(/last configuration change not recorded/i)).toBeInTheDocument()
  })

  it('shows Voice and SMS even when the service reports a Web channel (US-2.3)', async () => {
    store.conciergeStatus.channels = [
      { channel: 'voice', enabled: true, health: 'ok' },
      { channel: 'sms', enabled: true, health: 'degraded' },
      { channel: 'web', enabled: true, health: 'ok' },
    ]
    renderWithProviders(<ConciergeStatusCard />)

    const channels = await screen.findByRole('group', { name: 'Channels' })
    expect(within(channels).getByText('Voice')).toBeInTheDocument()
    expect(within(channels).getByText('SMS')).toBeInTheDocument()
    expect(within(channels).queryByText('Web')).not.toBeInTheDocument()
  })

  it('summarises connected systems with a health label, not colour alone', async () => {
    renderWithProviders(<ConciergeStatusCard />)

    const systems = await screen.findByRole('group', { name: 'Connected systems' })
    const scheduling = within(systems).getByText('Scheduling').closest('li')
    expect(scheduling).toHaveTextContent('Down')
    expect(within(systems).getByText('Payments').closest('li')).toHaveTextContent('Operational')
  })

  it('links to Configuration and to Test Concierge', async () => {
    renderWithProviders(<ConciergeStatusCard />)

    // The header link renders before the body loads; wait for the body's own.
    expect(await screen.findByRole('link', { name: 'Test Concierge' })).toHaveAttribute(
      'href',
      '/test',
    )
    expect(screen.getByRole('link', { name: 'View configuration' })).toHaveAttribute(
      'href',
      '/concierge/configuration',
    )
  })

  it('pauses only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    const pause = vi.spyOn(conciergeService, 'pause')
    renderWithProviders(<ConciergeStatusCard />)

    await user.click(await screen.findByRole('button', { name: 'Pause Concierge' }))
    await confirmDialog(user, 'Pause Concierge')

    expect(pause).toHaveBeenCalledOnce()
    expect(await screen.findByRole('status')).toHaveTextContent(/paused/i)
  })

  it('does not pause when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    const pause = vi.spyOn(conciergeService, 'pause')
    renderWithProviders(<ConciergeStatusCard />)

    await user.click(await screen.findByRole('button', { name: 'Pause Concierge' }))
    await confirmDialog(user, 'Cancel')

    expect(pause).not.toHaveBeenCalled()
  })

  it('offers Resume when Concierge is paused, and resumes without confirmation', async () => {
    const user = userEvent.setup()
    store.conciergeStatus.state = 'paused'
    const resume = vi.spyOn(conciergeService, 'resume')
    renderWithProviders(<ConciergeStatusCard />)

    await user.click(await screen.findByRole('button', { name: 'Resume Concierge' }))

    expect(resume).toHaveBeenCalledOnce()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the current state and warns when pausing fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(conciergeService, 'pause').mockRejectedValue(
      new AppError({
        kind: 'server',
        title: 'Something went wrong on our side',
        description: 'Concierge is still running. Try again in a moment.',
      }),
    )
    renderWithProviders(<ConciergeStatusCard />)

    await user.click(await screen.findByRole('button', { name: 'Pause Concierge' }))
    await confirmDialog(user, 'Pause Concierge')

    expect(await screen.findByRole('status')).toHaveTextContent(/still running/i)
    expect(screen.getByRole('button', { name: 'Pause Concierge' })).toBeInTheDocument()
  })

  it('updates the header badge, which reads the same query key', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <>
        <ConciergeStatusCard />
        <ConciergeStatusPanel />
      </>,
    )

    await screen.findByRole('button', { name: 'Concierge status: Active' })
    await user.click(screen.getByRole('button', { name: 'Pause Concierge' }))
    await confirmDialog(user, 'Pause Concierge')

    expect(
      await screen.findByRole('button', { name: 'Concierge status: Paused' }),
    ).toBeInTheDocument()
  })

  it('shows an error state with a retry when the status cannot be loaded', async () => {
    vi.spyOn(conciergeService, 'getStatus').mockRejectedValue(
      new AppError({
        kind: 'network',
        title: 'Cannot reach GuideAnts Concierge',
        description: 'Check your network connection and try again.',
        actions: [{ label: 'Retry', retry: true }],
      }),
    )
    renderWithProviders(<ConciergeStatusCard />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Check your network connection and try again.',
    )
  })
})
