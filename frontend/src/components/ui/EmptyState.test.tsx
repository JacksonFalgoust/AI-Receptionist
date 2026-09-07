import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

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
})
