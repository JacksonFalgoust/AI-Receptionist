import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Avatar } from './Avatar'

describe('Avatar', () => {
  it('renders initials from a two-word name, with the full name as the accessible name', () => {
    render(<Avatar name="Dana Ortiz" />)
    expect(screen.getByRole('img', { name: 'Dana Ortiz' })).toHaveTextContent('DO')
  })

  it('renders a single initial for a one-word name', () => {
    render(<Avatar name="Cher" />)
    expect(screen.getByRole('img', { name: 'Cher' })).toHaveTextContent('C')
  })

  it('renders an actual image when imageUrl is given', () => {
    render(<Avatar name="Dana Ortiz" imageUrl="https://example.com/dana.png" />)
    expect(screen.getByRole('img', { name: 'Dana Ortiz' })).toHaveAttribute(
      'src',
      'https://example.com/dana.png',
    )
  })
})
