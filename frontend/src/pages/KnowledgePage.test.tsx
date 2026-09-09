import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { KnowledgePage } from './KnowledgePage'

describe('KnowledgePage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<KnowledgePage />)

    expect(screen.getByRole('heading', { name: 'Knowledge' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('keeps loading, empty, error and success states inside the same panel frame', async () => {
    renderWithProviders(<KnowledgePage />)

    // The skeleton must already sit inside the panel border, or the page
    // reflows the moment the rows land.
    expect(screen.getByTestId('knowledge-panel')).toContainElement(screen.getByRole('status'))

    await screen.findByRole('table')
    expect(screen.getByTestId('knowledge-panel')).toContainElement(screen.getByRole('table'))
  })

  it('keys its list query [knowledge, list, params], matching the rest of the app', async () => {
    const { queryClient } = renderWithProviders(<KnowledgePage />)
    await screen.findByRole('table')

    expect(queryClient.getQueryCache().findAll({ queryKey: ['knowledge', 'list'] })).toHaveLength(1)
  })

  it('pages through the library rather than loading it whole', async () => {
    renderWithProviders(<KnowledgePage />)

    // More than one page must actually exist, or the control is decoration.
    expect(await screen.findByText(/Page 1 of 2/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()
  })

  it('narrows the list when a filter is applied', async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgePage />)
    await screen.findByRole('table')

    await user.selectOptions(screen.getByLabelText('Type'), 'policy')

    expect(await screen.findByText(/Page 1 of 1/)).toBeInTheDocument()
  })

  it('says plainly when a filter matches nothing, and offers a way back', async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgePage />, {
      route: '/concierge/knowledge?q=nothingmatchesthisstring',
    })

    expect(await screen.findByText('No knowledge matches these filters')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('invites a first entry when the library is empty, in the words PRD §25 uses', async () => {
    store.knowledge.length = 0
    renderWithProviders(<KnowledgePage />)

    expect(await screen.findByText('Give Concierge something to work with')).toBeInTheDocument()
    expect(
      screen.getByText('Add FAQs, policies, services, documents, and other business information.'),
    ).toBeInTheDocument()
  })

  it('lands a bookmarked page beyond the result set on the last real page, with rows', async () => {
    // The library shrank since the link was saved. Showing "Page 99 of 2"
    // over an empty table, with Previous stepping back one page at a time,
    // is 97 clicks from anything — so the page corrects itself to the last
    // page that exists and shows its rows, and never reads as an empty
    // library when 34 real items sit behind it.
    renderWithProviders(<KnowledgePage />, { route: '/concierge/knowledge?page=99' })

    expect(await screen.findByText('Page 2 of 2 · 34 total')).toBeInTheDocument()
    expect(screen.getAllByRole('row').length).toBeGreaterThan(1)
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(screen.queryByText('Give Concierge something to work with')).not.toBeInTheDocument()
  })

  it('returns to the first page when a filter changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<KnowledgePage />, { route: '/concierge/knowledge?page=2' })
    expect(await screen.findByText(/Page 2 of 2/)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Status'), 'active')

    expect(await screen.findByText(/Page 1 of/)).toBeInTheDocument()
  })

  it('offers a way to add knowledge from the page header', async () => {
    renderWithProviders(<KnowledgePage />)
    await screen.findByRole('table')

    expect(screen.getByRole('button', { name: 'Add knowledge' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upload document' })).toBeInTheDocument()
  })

  it('offers the add actions from the empty state too, not just the header', async () => {
    // An empty library is exactly when someone needs the CTA most.
    store.knowledge.length = 0
    renderWithProviders(<KnowledgePage />)

    await screen.findByText('Give Concierge something to work with')

    // Scoped to the panel: the page header's menu is always there, so an
    // unscoped query would pass without the empty state offering anything.
    const panel = within(screen.getByTestId('knowledge-panel'))
    expect(panel.getByRole('link', { name: 'Add knowledge' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new',
    )
  })
})
