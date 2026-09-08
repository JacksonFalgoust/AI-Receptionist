import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { StatusPill } from './StatusPill'

describe('StatusPill', () => {
  it('renders the human-readable label as text, not just a colored dot', () => {
    render(<StatusPill status="setup_required" />)
    expect(screen.getByText('Setup required')).toBeInTheDocument()
  })

  it('renders a different label for a different status', () => {
    render(<StatusPill status="connected" />)
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })
})
