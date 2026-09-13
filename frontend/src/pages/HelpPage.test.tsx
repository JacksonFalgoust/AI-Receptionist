import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/renderWithProviders'

import { HelpPage } from './HelpPage'

describe('HelpPage', () => {
  it('renders all four cards by default', () => {
    renderWithProviders(<HelpPage />)
    expect(screen.getByText('Getting started')).toBeInTheDocument()
    expect(screen.getByText('Configuration guides')).toBeInTheDocument()
    expect(screen.getByText('Integration guides')).toBeInTheDocument()
    expect(screen.getByLabelText('Contact support')).toBeInTheDocument()
  })

  it('filters to a single card by description text', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HelpPage />)

    // "CRM" appears only in Integration guides' description.
    await user.type(screen.getByLabelText('Search help'), 'CRM')

    expect(screen.getByText('Integration guides')).toBeInTheDocument()
    expect(screen.queryByText('Getting started')).not.toBeInTheDocument()
    expect(screen.queryByText('Configuration guides')).not.toBeInTheDocument()
    expect(screen.queryByText('Contact support')).not.toBeInTheDocument()
  })

  it('shows an empty state when nothing matches', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HelpPage />)

    await user.type(screen.getByLabelText('Search help'), 'nonexistent-term')

    expect(screen.getByText('No results')).toBeInTheDocument()
    expect(screen.queryByText('Getting started')).not.toBeInTheDocument()
  })

  it('restores all four cards when the search is cleared', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HelpPage />)

    const searchField = screen.getByLabelText('Search help')
    await user.type(searchField, 'CRM')
    expect(screen.queryByText('Getting started')).not.toBeInTheDocument()

    await user.clear(searchField)
    expect(screen.getByText('Getting started')).toBeInTheDocument()
  })
})
