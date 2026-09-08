import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Skeleton } from './Skeleton'

describe('Skeleton', () => {
  it('announces itself as a loading status', () => {
    render(<Skeleton />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('renders the requested number of placeholder rows for the text variant', () => {
    const { container } = render(<Skeleton variant="text" rows={4} />)
    expect(container.querySelectorAll('[data-skeleton-row]')).toHaveLength(4)
  })

  it('renders a single block for the card variant', () => {
    const { container } = render(<Skeleton variant="card" />)
    expect(container.querySelectorAll('[data-skeleton-row]')).toHaveLength(0)
  })
})
