import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { SectionHeader } from './SectionHeader'

describe('SectionHeader', () => {
  it('renders the title as an h2', () => {
    render(<SectionHeader title="Recent escalations" />)
    expect(screen.getByRole('heading', { level: 2, name: 'Recent escalations' })).toBeInTheDocument()
  })
})
