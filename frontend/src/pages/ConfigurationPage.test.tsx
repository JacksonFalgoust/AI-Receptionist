import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { conciergeService } from '@/services/conciergeService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ConfigurationPage } from './ConfigurationPage'

describe('ConfigurationPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('is a built screen, not a placeholder, opening on the Business profile tab', async () => {
    renderWithProviders(<ConfigurationPage />)
    expect(screen.getByRole('heading', { name: 'Configuration' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByDisplayValue('Horizon Partners')).toBeInTheDocument()
  })

  it('loads behind a loading state', async () => {
    renderWithProviders(<ConfigurationPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('Horizon Partners')).toBeInTheDocument()
  })

  it('switches to the Identity tab and shows its fields', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('tab', { name: 'Identity' }))
    expect(screen.getByDisplayValue('Horizon Concierge')).toBeInTheDocument()
  })

  it('switches to the Terminology tab and shows its fields', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('tab', { name: 'Terminology' }))
    expect(screen.getByDisplayValue('Client')).toBeInTheDocument()
  })

  it('Preview shows the saved greeting, not an unsaved edit', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('tab', { name: 'Identity' }))
    const greeting = screen.getByLabelText('Greeting')
    await user.clear(greeting)
    await user.type(greeting, 'An edit nobody saved yet.')

    await user.click(screen.getByRole('tab', { name: 'Preview' }))
    expect(screen.queryByText('An edit nobody saved yet.')).not.toBeInTheDocument()
    expect(
      screen.getByText('Thanks for contacting Horizon Partners. How can I help today?'),
    ).toBeInTheDocument()
  })

  it('"Preview greeting" switches to the Preview tab', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('tab', { name: 'Identity' }))
    await user.click(screen.getByRole('button', { name: 'Preview greeting' }))
    expect(screen.getByRole('tab', { name: 'Preview' })).toHaveAttribute('aria-selected', 'true')
  })

  it('disables Publish while Save draft is in flight, so a second click cannot race it', async () => {
    const user = userEvent.setup()
    let resolveSave: (value: typeof store.conciergeConfiguration) => void = () => {}
    vi.spyOn(conciergeService, 'saveDraft').mockReturnValue(
      new Promise((resolve) => {
        resolveSave = resolve
      }),
    )

    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Publish changes' })).toBeDisabled()

    resolveSave(store.conciergeConfiguration)
    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Publish changes' })).toBeEnabled()
  })

  it('saves a change to the draft, toasts, shows the unpublished-changes banner, and does not publish', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)

    const name = await screen.findByDisplayValue('Horizon Partners')
    await user.clear(name)
    await user.type(name, 'Meridian Partners')
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(await screen.findByText('Draft saved.')).toBeInTheDocument()
    expect(store.conciergeConfiguration.businessProfile.name).toBe('Meridian Partners')
    expect(store.conciergeConfiguration.hasUnpublishedChanges).toBe(true)
    expect(
      screen.getByText(/draft changes that have not been published yet/i),
    ).toBeInTheDocument()
  })

  it('flags the Identity tab with an error found while viewing Business profile', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('tab', { name: 'Identity' }))
    const identityName = screen.getByLabelText('Concierge name')
    await user.clear(identityName)

    await user.click(screen.getByRole('tab', { name: 'Business profile' }))
    await user.click(screen.getByRole('button', { name: 'Save draft' }))

    expect(await screen.findByRole('tab', { name: /Identity/ })).toHaveTextContent(/has an error/i)
    expect(screen.getByRole('tab', { name: 'Business profile' })).not.toHaveTextContent(
      /has an error/i,
    )
    // The error lives on a tab the user isn't looking at — silence here would
    // read as "the button did nothing."
    expect(await screen.findByText(/Fix the highlighted tab/i)).toBeInTheDocument()
  })

  it('publishes only after confirming, and never on Save draft alone', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConfigurationPage />)
    await screen.findByDisplayValue('Horizon Partners')

    await user.click(screen.getByRole('button', { name: 'Publish changes' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Cancel' }))
    expect(store.conciergeConfiguration.hasUnpublishedChanges).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Publish changes' }))
    const confirmDialog = within(await screen.findByRole('dialog'))
    await user.click(confirmDialog.getByRole('button', { name: 'Publish' }))

    expect(await screen.findByText('Configuration published.')).toBeInTheDocument()
    expect(store.conciergeConfiguration.hasUnpublishedChanges).toBe(false)
    expect(store.conciergeConfiguration.lastPublishedAt).toBeTruthy()
  })
})
