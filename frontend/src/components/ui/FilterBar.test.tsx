import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { FilterBar } from './FilterBar'

describe('FilterBar', () => {
  it('renders its filter controls', () => {
    render(
      <FilterBar>
        <label>Channel</label>
      </FilterBar>,
    )
    expect(screen.getByText('Channel')).toBeInTheDocument()
  })

  it('disables Clear filters when there are none active, and calls onClear when there are', async () => {
    const user = userEvent.setup()
    const onClear = vi.fn()
    const { rerender } = render(<FilterBar onClear={onClear}>filters</FilterBar>)
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled()

    rerender(
      <FilterBar onClear={onClear} hasActiveFilters>
        filters
      </FilterBar>,
    )
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('renders no Clear filters button when onClear is not given', () => {
    render(<FilterBar>filters</FilterBar>)
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
  })
})
