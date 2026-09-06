import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Badge } from './Badge'

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge tone="info">Owner</Badge>)
    expect(screen.getByText('Owner')).toBeInTheDocument()
  })

  it('defaults to a muted tone when none is given', () => {
    render(<Badge>3</Badge>)
    expect(screen.getByText('3')).toHaveClass('bg-canvas-tint')
  })
})
