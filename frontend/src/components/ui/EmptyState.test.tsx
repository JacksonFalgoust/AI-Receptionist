import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(
      <EmptyState
        title="Give Concierge something to work with"
        description="Add an FAQ, a policy, or a document."
      />,
    )
    expect(screen.getByText('Give Concierge something to work with')).toBeInTheDocument()
    expect(screen.getByText('Add an FAQ, a policy, or a document.')).toBeInTheDocument()
  })

  it('renders an action button that calls its handler', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<EmptyState title="No workflows yet" action={{ label: 'Create your first workflow', onClick }} />)
    await user.click(screen.getByRole('button', { name: 'Create your first workflow' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders an action that navigates as a link, not a button', () => {
    // A CTA that goes somewhere has to be a real link: a button cannot be
    // opened in a new tab and does not announce itself as a destination.
    render(
      <MemoryRouter>
        <EmptyState title="Give Concierge something to work with" action={{ label: 'Add knowledge', href: '/concierge/knowledge/new' }} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Add knowledge' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new',
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
