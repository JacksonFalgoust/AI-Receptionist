import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { KnowledgeFilterBar } from './KnowledgeFilterBar'
import type { KnowledgeFilterState } from './useKnowledgeFilters'

const empty: KnowledgeFilterState = { search: '', page: 1 }

function renderBar(state: Partial<KnowledgeFilterState> = {}) {
  const onChange = vi.fn()
  const onClear = vi.fn()
  const merged = { ...empty, ...state }
  const activeCount = [merged.search !== '', merged.type, merged.status].filter(Boolean).length

  render(
    <KnowledgeFilterBar
      state={merged}
      activeCount={activeCount}
      onChange={onChange}
      onClear={onClear}
    />,
  )
  return { onChange, onClear }
}

describe('KnowledgeFilterBar', () => {
  it('offers every type, so nothing in the library is unreachable by filter', () => {
    renderBar()
    const options = within(screen.getByLabelText('Type'))
      .getAllByRole('option')
      .map((option) => option.textContent)

    // Ten types plus the "Any type" default.
    expect(options).toHaveLength(11)
    expect(options).toContain('Uploaded document')
    expect(options).toContain('Website content')
  })

  it('offers all five statuses US-5.1 lists', () => {
    renderBar()
    const options = within(screen.getByLabelText('Status'))
      .getAllByRole('option')
      .map((option) => option.textContent)

    expect(options).toEqual([
      'Any status',
      'Active',
      'Processing',
      'Needs review',
      'Error',
      'Disabled',
    ])
  })

  it('reports a chosen type to the caller', async () => {
    const user = userEvent.setup()
    const { onChange } = renderBar()

    await user.selectOptions(screen.getByLabelText('Type'), 'policy')

    expect(onChange).toHaveBeenCalledWith({ type: 'policy' })
  })

  it('treats the any-type option as clearing the filter', async () => {
    const user = userEvent.setup()
    const { onChange } = renderBar({ type: 'policy' })

    await user.selectOptions(screen.getByLabelText('Type'), '')

    expect(onChange).toHaveBeenCalledWith({ type: undefined })
  })

  it('shows what is currently in force as removable chips', async () => {
    const user = userEvent.setup()
    const { onChange } = renderBar({ type: 'faq', status: 'needs_review' })

    const chips = within(screen.getByRole('list', { name: 'Active filters' }))
    expect(chips.getByText('Type: FAQ')).toBeInTheDocument()
    expect(chips.getByText('Status: Needs review')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove Type filter' }))
    expect(onChange).toHaveBeenCalledWith({ type: undefined })
  })

  it('shows no chips when nothing is filtered', () => {
    renderBar()
    expect(screen.queryByRole('list', { name: 'Active filters' })).not.toBeInTheDocument()
  })

  it('cannot clear filters that are not set', () => {
    renderBar()
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled()
  })

  it('clears everything at once', async () => {
    const user = userEvent.setup()
    const { onClear } = renderBar({ search: 'refund', type: 'policy' })

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(onClear).toHaveBeenCalled()
  })

  it('echoes typing immediately but only searches once typing stops', async () => {
    const user = userEvent.setup()
    const { onChange } = renderBar()

    await user.type(screen.getByLabelText('Search knowledge'), 'refund')

    // The box must feel responsive while the query behind it waits.
    expect(screen.getByLabelText('Search knowledge')).toHaveValue('refund')
    expect(onChange).not.toHaveBeenCalledWith({ search: 'refund' })

    expect(await screen.findByDisplayValue('refund')).toBeInTheDocument()
    await vi.waitFor(() => expect(onChange).toHaveBeenCalledWith({ search: 'refund' }))
  })
})
