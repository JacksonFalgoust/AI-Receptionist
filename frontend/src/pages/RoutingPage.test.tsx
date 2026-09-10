import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { routingService } from '@/services/routingService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { RoutingPage } from './RoutingPage'

describe('RoutingPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<RoutingPage />)
    expect(screen.getByRole('heading', { name: 'Escalation & Routing' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByText('Client asks for a person')).toBeInTheDocument()
  })

  it('loads behind a loading state', async () => {
    renderWithProviders(<RoutingPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByText('Client asks for a person')).toBeInTheDocument()
  })

  it('counts the rules that are actually routing', async () => {
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')
    const active = store.routingRules.filter((rule) => rule.enabled).length
    expect(screen.getByText('Active rules').closest('div')).toHaveTextContent(String(active))
  })

  it('reports escalations today', async () => {
    renderWithProviders(<RoutingPage />)
    expect(await screen.findByText('Escalations today')).toBeInTheDocument()
  })

  it('renders one row per seeded rule', async () => {
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')
    // One row per rule, plus the header row.
    expect(screen.getAllByRole('row')).toHaveLength(store.routingRules.length + 1)
  })

  it('invites a first rule when there are none', async () => {
    store.routingRules = []
    renderWithProviders(<RoutingPage />)
    expect(await screen.findByText('Create your first routing rule')).toBeInTheDocument()
  })

  it('explains a failure to load', async () => {
    vi.spyOn(routingService, 'list').mockRejectedValueOnce(
      new AppError({
        kind: 'server',
        title: 'Could not load routing rules',
        description: 'Try again in a moment.',
      }),
    )
    renderWithProviders(<RoutingPage />)
    expect(await screen.findByText('Could not load routing rules')).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  it('adds a rule from the page header', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')

    await user.click(screen.getByRole('button', { name: 'Add rule' }))

    expect(await screen.findByRole('heading', { name: 'Add rule' })).toBeInTheDocument()
  })

  it('starts a new rule after the rules that already exist', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')

    await user.click(screen.getByRole('button', { name: 'Add rule' }))

    expect(await screen.findByLabelText('Priority')).toHaveValue(
      store.routingRules.length + 1,
    )
  })

  it('opens an existing rule for editing', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')

    const row = screen.getByRole('row', { name: /Client asks for a person/ })
    await user.click(within(row).getByRole('button', { name: 'Edit' }))

    expect(await screen.findByRole('heading', { name: 'Edit rule' })).toBeInTheDocument()
    expect(screen.getByLabelText('Rule name')).toHaveValue('Client asks for a person')
  })

  it('offers a first rule from the empty state', async () => {
    const user = userEvent.setup()
    store.routingRules = []
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Create your first routing rule')

    // Two buttons carry this label once the catalog is empty — the page
    // header's and the empty state's CTA. The empty state's is the one under
    // test, and it renders last.
    const addButtons = screen.getAllByRole('button', { name: 'Add rule' })
    expect(addButtons).toHaveLength(2)
    await user.click(addButtons[addButtons.length - 1])

    expect(await screen.findByRole('heading', { name: 'Add rule' })).toBeInTheDocument()
  })
})
