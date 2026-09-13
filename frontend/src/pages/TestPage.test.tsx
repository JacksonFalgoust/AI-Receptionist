import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/renderWithProviders'

import { TestPage } from './TestPage'

describe('TestPage', () => {
  it('renders the panel content in a page shell, not drawer chrome', () => {
    renderWithProviders(<TestPage />)

    expect(screen.getByRole('heading', { name: 'Test Concierge' })).toBeInTheDocument()
    expect(screen.getByText('TEST MODE')).toBeInTheDocument()
    expect(screen.getByText('Send a message to try out your Concierge.')).toBeInTheDocument()
    // A page, not a dialog: no Drawer/Modal chrome wraps this content.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
