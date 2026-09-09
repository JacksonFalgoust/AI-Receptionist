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

  it('returns to the first page when a filter changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ConversationsPage />, { route: '/conversations?page=3' })
    expect(await screen.findByText(/Page 3 of 3/)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Channel'), 'voice')

    expect(await screen.findByText(/Page 1 of/)).toBeInTheDocument()
  })
})
