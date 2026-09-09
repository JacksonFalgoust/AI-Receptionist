import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ConversationFilterBar } from './ConversationFilterBar'
import type { ConversationFilterState } from './useConversationFilters'

const EMPTY: ConversationFilterState = { search: '', range: 'any', page: 1 }

const OPTIONS = {
  intents: ['Billing question', 'Book appointment'],
  locations: [{ id: 'loc_north', name: 'North Office' }],
  employees: ['Sam Rivera'],
}

function setup(state: ConversationFilterState = EMPTY) {
  const onChange = vi.fn()
  const onClear = vi.fn()
  const view = render(
    <ConversationFilterBar
      state={state}
      options={OPTIONS}
      activeCount={state === EMPTY ? 0 : 1}
      onChange={onChange}
      onClear={onClear}
    />,
  )
  return { onChange, onClear, user: userEvent.setup(), rerender: view.rerender }
}

describe('ConversationFilterBar', () => {
  it('shows the four primary filters without disclosure', () => {
    setup()
    expect(screen.getByRole('textbox', { name: /search conversations/i })).toBeInTheDocument()
    expect(screen.getByLabelText('Channel')).toBeInTheDocument()
    expect(screen.getByLabelText('Outcome')).toBeInTheDocument()
    expect(screen.getByLabelText('Escalated')).toBeInTheDocument()
  })

  it('keeps the remaining filters behind More filters until asked', async () => {
    const { user } = setup()
    expect(screen.queryByLabelText('Intent')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /more filters/i }))

    expect(screen.getByLabelText('Date range')).toBeInTheDocument()
    expect(screen.getByLabelText('Intent')).toBeInTheDocument()
    expect(screen.getByLabelText('Location')).toBeInTheDocument()
    expect(screen.getByLabelText('Assigned employee')).toBeInTheDocument()
  })

  it('reports a channel choice', async () => {
    const { onChange, user } = setup()
    await user.selectOptions(screen.getByLabelText('Channel'), 'sms')
    expect(onChange).toHaveBeenCalledWith({ channel: 'sms' })
  })

  it('turns the Escalated select back into a boolean', async () => {
    const { onChange, user } = setup()
    await user.selectOptions(screen.getByLabelText('Escalated'), 'true')
    expect(onChange).toHaveBeenCalledWith({ escalated: true })
  })

  it('offers intents supplied by the service, not invented ones', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: /more filters/i }))
    expect(screen.getByRole('option', { name: 'Billing question' })).toBeInTheDocument()
  })

  it('shows an applied filter as a chip that can be removed', async () => {
    const { onChange, user } = setup({ ...EMPTY, channel: 'voice' })
    await user.click(screen.getByRole('button', { name: 'Remove Channel filter' }))
    expect(onChange).toHaveBeenCalledWith({ channel: undefined })
  })

  it('clears everything at once', async () => {
    const { onClear, user } = setup({ ...EMPTY, channel: 'voice' })
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(onClear).toHaveBeenCalled()
  })

  it('does not report a search change until the debounce window elapses', () => {
    vi.useFakeTimers()
    const { onChange } = setup()
    const input = screen.getByRole('textbox', { name: /search conversations/i })

    fireEvent.change(input, { target: { value: 'refund' } })
    expect(onChange).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(onChange).toHaveBeenCalledWith({ search: 'refund' })
    vi.useRealTimers()
  })

  it('empties the visible search box when filters are cleared externally', () => {
    const { rerender } = setup({ ...EMPTY, search: 'refund' })
    const input = screen.getByRole('textbox', { name: /search conversations/i })
    expect(input).toHaveValue('refund')

    rerender(
      <ConversationFilterBar
        state={EMPTY}
        options={OPTIONS}
        activeCount={0}
        onChange={vi.fn()}
        onClear={vi.fn()}
      />,
    )

    expect(input).toHaveValue('')
  })

  it('gives the More filters button aria-controls pointing at the disclosed group', async () => {
    const { user } = setup()
    const button = screen.getByRole('button', { name: /more filters/i })
    const controlsId = button.getAttribute('aria-controls')
    expect(controlsId).toBeTruthy()

    await user.click(button)

    expect(document.getElementById(controlsId!)).toContainElement(
      screen.getByLabelText('Date range'),
    )
  })
})
