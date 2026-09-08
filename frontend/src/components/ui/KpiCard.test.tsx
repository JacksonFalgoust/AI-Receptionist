import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { KpiCard } from './KpiCard'

describe('KpiCard', () => {
  it('renders the label and value, and only the label and value', () => {
    render(<KpiCard label="Conversations Today" value={128} />)
    expect(screen.getByText('Conversations Today')).toBeInTheDocument()
    expect(screen.getByText('128')).toBeInTheDocument()
  })
})
