import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'

import { resetStore } from '@/mocks/store'
import { paths } from '@/routes/paths'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ConversationDetailPage } from './ConversationDetailPage'

/** The page reads its id from the route, so it needs a real route match. */
function renderAt(id: string) {
  return renderWithProviders(
    <Routes>
      <Route path={paths.conversation()} element={<ConversationDetailPage />} />
    </Routes>,
    { route: `/conversations/${id}` },
  )
}

describe('ConversationDetailPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderAt('conv_0002')

    expect(await screen.findByRole('heading', { name: 'Dana Wu' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
  })

  it('leads with a breadcrumb back to Conversations', async () => {
    renderAt('conv_0002')

    await screen.findByRole('heading', { name: 'Dana Wu' })
    const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(breadcrumb).toHaveTextContent('Conversations')
    expect(screen.getByRole('link', { name: 'Conversations' })).toHaveAttribute(
      'href',
      '/conversations',
    )
  })

  it('summarises the interaction in business language (US-3.2)', async () => {
    renderAt('conv_0002')

    expect(await screen.findByRole('heading', { name: 'Summary' })).toBeInTheDocument()
    expect(screen.getByText(/Dana Wu contacted Concierge about/i)).toBeInTheDocument()
  })

  it('shows the transcript and the action timeline together', async () => {
    renderAt('conv_0002')

    expect(await screen.findByRole('heading', { name: 'Transcript' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Action Timeline' })).toBeInTheDocument()
    expect(screen.getByText('Look up customer')).toBeInTheDocument()
  })

  it('explains a conversation that does not exist, and offers a way back', async () => {
    renderAt('conv_9999')

    expect(await screen.findByText('Conversation not found')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to conversations' })).toHaveAttribute(
      'href',
      '/conversations',
    )
  })
})
