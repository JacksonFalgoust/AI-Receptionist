import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { PageHeader } from './PageHeader'

describe('PageHeader', () => {
  it('renders the title as an h1, plus description and actions', () => {
    render(
      <PageHeader
        title="Conversations"
        description="Every call and message Concierge has handled."
        actions={<button>Export</button>}
      />,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Conversations' })).toBeInTheDocument()
    expect(
      screen.getByText('Every call and message Concierge has handled.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument()
  })
})
