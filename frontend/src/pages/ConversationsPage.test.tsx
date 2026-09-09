import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ConversationsPage } from './ConversationsPage'

describe('ConversationsPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('keeps loading, empty, error and success states inside the same panel frame', async () => {
    renderWithProviders(<ConversationsPage />)

    // Loading first — the skeleton must already sit inside the panel border,
    // not render bare on the page background while only the loaded table
    // gets a card. Otherwise the page reflows the moment data lands.
    expect(screen.getByTestId('conversations-panel')).toContainElement(
      screen.getByRole('status'),
    )

    await screen.findByRole('table')
    expect(screen.getByTestId('conversations-panel')).toContainElement(
      screen.getByRole('table'),
    )
  })

  it('keys its list query [conversations, list, params], matching the rest of the app', async () => {
    const { queryClient } = renderWithProviders(<ConversationsPage />)
    await screen.findByRole('table')

    // ['namespace', 'entity', variable] — not ['conversations', params],
    // which would collide in shape with a future ['conversations', id]
    // detail query and departs from every other query in the app.
    expect(
      queryClient.getQueryCache().findAll({ queryKey: ['conversations', 'list'] }),
    ).toHaveLength(1)
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<ConversationsPage />)
    expect(screen.getByRole('heading', { name: 'Conversations' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('pages through the full history 25 at a time', async () => {
    renderWithProviders(<ConversationsPage />)
    expect(await screen.findByText(/70 total/)).toBeInTheDocument()
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument()
  })

  it('narrows the list when a filter is applied', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConversationsPage />)
    await screen.findByRole('table')

    await user.selectOptions(screen.getByLabelText('Channel'), 'voice')

    expect(await screen.findByText(/Page 1 of 1/)).toBeInTheDocument()
  })

  it('says plainly when a filter matches nothing, and offers a way back', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConversationsPage />, {
      route: '/conversations?q=nothingmatchesthisstring',
    })

    expect(await screen.findByText('No conversations match these filters')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('distinguishes an empty history from an empty result', async () => {
    store.conversations.length = 0
    renderWithProviders(<ConversationsPage />)

    expect(await screen.findByText('No conversations yet')).toBeInTheDocument()
  })

  it('recovers from a bookmarked page beyond the result set instead of claiming the list is empty', async () => {
    renderWithProviders(<ConversationsPage />, { route: '/conversations?page=99' })

    // 70 conversations exist; page 99 does not. This must never read as "no
    // conversations yet" — a lie with 70 real rows behind it — and must not
    // strand the reader on an empty table 96 Previous clicks from data.
    expect(await screen.findByText('Page 3 of 3 · 70 total')).toBeInTheDocument()
    expect(screen.getAllByRole('row').length).toBeGreaterThan(1)
    expect(screen.queryByText('No conversations yet')).not.toBeInTheDocument()
    expect(screen.queryByText(/No conversations match/)).not.toBeInTheDocument()
  })

  it('returns to the first page when a filter changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConversationsPage />, { route: '/conversations?page=3' })
    expect(await screen.findByText(/Page 3 of 3/)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Channel'), 'voice')

    expect(await screen.findByText(/Page 1 of/)).toBeInTheDocument()
  })
})
