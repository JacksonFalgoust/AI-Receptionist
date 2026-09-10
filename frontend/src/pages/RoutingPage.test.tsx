import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { routingService } from '@/services/routingService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { RoutingRule } from '@/types'

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

    // `setEditingRule` is a synchronous state update and `Modal` renders its
    // heading with no animation or async gap — this is correct on the first
    // render, but flaked once under CI's shared-runner load against RTL's
    // default 1000ms findBy timeout, so it's given more room rather than
    // treated as a real race.
    expect(await screen.findByRole('heading', { name: 'Edit rule' }, { timeout: 3000 })).toBeInTheDocument()
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

  it('keeps an in-progress new rule when the rules query settles after the modal opens', async () => {
    const user = userEvent.setup()
    let resolveList!: (rules: RoutingRule[]) => void
    const pending = new Promise<RoutingRule[]>((resolve) => {
      resolveList = resolve
    })
    // Holds the rules query open, so "Add rule" is clicked while
    // `rulesQuery.data` is still undefined — the exact window in which
    // `defaultPriority` used to be computed as `0 + 1` and then jump once the
    // query resolved out from under the still-open modal.
    vi.spyOn(routingService, 'list').mockReturnValueOnce(pending)

    renderWithProviders(<RoutingPage />)

    await user.click(screen.getByRole('button', { name: 'Add rule' }))
    expect(await screen.findByRole('heading', { name: 'Add rule' })).toBeInTheDocument()
    expect(screen.getByLabelText('Priority')).toHaveValue(1)

    await user.type(screen.getByLabelText('Rule name'), 'Drafted while loading')

    // The rules query resolves in the background while the modal is still
    // open — this must not reset the form the user is mid-way through.
    resolveList([...store.routingRules].sort((a, b) => a.priority - b.priority))
    await screen.findByText('Client asks for a person')

    expect(screen.getByLabelText('Rule name')).toHaveValue('Drafted while loading')
    vi.restoreAllMocks()
  })
})
