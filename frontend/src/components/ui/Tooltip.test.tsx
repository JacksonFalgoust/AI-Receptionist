import { describe, expect, it, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'

import { Tooltip } from './Tooltip'

describe('Tooltip', () => {
  it('shows the tooltip after a hover delay and hides it on mouse leave', async () => {
    vi.useFakeTimers()
    render(
      <Tooltip content="Send a test message">
        <button>Test</button>
      </Tooltip>,
    )
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()

    const button = screen.getByRole('button', { name: 'Test' })
    fireEvent.mouseEnter(button)
    await act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByRole('tooltip')).toHaveTextContent('Send a test message')

    fireEvent.mouseLeave(button)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('wires aria-describedby onto the trigger while visible', async () => {
    vi.useFakeTimers()
    render(
      <Tooltip content="Send a test message">
        <button>Test</button>
      </Tooltip>,
    )
    const button = screen.getByRole('button', { name: 'Test' })
    fireEvent.mouseEnter(button)
    await act(() => {
      vi.advanceTimersByTime(300)
    })
    const tooltip = screen.getByRole('tooltip')
    expect(button).toHaveAttribute('aria-describedby', tooltip.id)
    vi.useRealTimers()
  })

  it('never shows the tooltip if the pointer leaves before the delay elapses', async () => {
    vi.useFakeTimers()
    render(
      <Tooltip content="Send a test message">
        <button>Test</button>
      </Tooltip>,
    )
    const button = screen.getByRole('button', { name: 'Test' })

    fireEvent.mouseEnter(button)
    fireEvent.mouseLeave(button)
    await act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    vi.useRealTimers()
  })
})
