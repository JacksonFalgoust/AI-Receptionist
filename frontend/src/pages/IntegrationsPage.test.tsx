import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { IntegrationsPage } from './IntegrationsPage'

describe('IntegrationsPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<IntegrationsPage />)
    expect(screen.getByRole('heading', { name: 'Integrations' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Customer Records' })).toBeInTheDocument()
  })

  it('loads behind a loading state', async () => {
    renderWithProviders(<IntegrationsPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Customer Records' })).toBeInTheDocument()
  })

  it('renders one card per seeded integration', async () => {
    renderWithProviders(<IntegrationsPage />)
    await screen.findByRole('heading', { name: 'Customer Records' })
    expect(screen.getAllByRole('group')).toHaveLength(store.integrations.length)
  })

  it('narrows the grid to the selected category', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IntegrationsPage />)
    await screen.findByRole('heading', { name: 'Customer Records' })

    await user.selectOptions(screen.getByLabelText('Category'), 'crm')

    expect(screen.getAllByRole('group')).toHaveLength(1)
    expect(screen.getByRole('heading', { name: 'Customer Records' })).toBeInTheDocument()
  })

  it('says plainly when a category has no connections, and offers a way back', async () => {
    const user = userEvent.setup()
    // No seeded integration is in the 'crm' category, so filtering to it is
    // the "filter matches nothing" case rather than the whole-catalog empty.
    store.integrations = store.integrations.filter((integration) => integration.category !== 'crm')
    renderWithProviders(<IntegrationsPage />)
    await screen.findByLabelText('Category')

    await user.selectOptions(screen.getByLabelText('Category'), 'crm')

    expect(await screen.findByText('No integrations in this category')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(await screen.findByRole('heading', { name: 'Scheduling' })).toBeInTheDocument()
  })

  it('invites a first connection when the catalog is empty, in the words PRD §17 uses', async () => {
    store.integrations.length = 0
    renderWithProviders(<IntegrationsPage />)

    expect(await screen.findByText('Connect your first business system')).toBeInTheDocument()
  })

  it('still invites a first connection when the catalog is empty and a category is selected', async () => {
    // A stale category filter must not hide the true-empty message behind
    // "try a different category" — there is nothing to connect at all.
    store.integrations.length = 0
    renderWithProviders(<IntegrationsPage />, { route: '/' })
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('Category'), 'crm')

    expect(await screen.findByText('Connect your first business system')).toBeInTheDocument()
  })
})
