import { useRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { useFocusTrap } from './useFocusTrap'

function Harness({ onEscape }: { onEscape: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(false)
  useFocusTrap(containerRef, active, () => {
    onEscape()
    setActive(false)
  })

  return (
    <div>
      <button onClick={() => setActive(true)}>Trigger</button>
      {active ? (
        <div ref={containerRef} tabIndex={-1}>
          <button>First</button>
          <button>Last</button>
        </div>
      ) : null}
    </div>
  )
}

describe('useFocusTrap', () => {
  it('moves focus into the container and traps Tab at the edges', async () => {
    const user = userEvent.setup()
    render(<Harness onEscape={vi.fn()} />)
    await user.click(screen.getByText('Trigger'))

    expect(screen.getByText('First')).toHaveFocus()
    await user.tab()
    expect(screen.getByText('Last')).toHaveFocus()
    await user.tab()
    expect(screen.getByText('First')).toHaveFocus()
  })

  it('traps Shift+Tab backwards from the first element to the last', async () => {
    const user = userEvent.setup()
    render(<Harness onEscape={vi.fn()} />)
    await user.click(screen.getByText('Trigger'))

    expect(screen.getByText('First')).toHaveFocus()
    await user.tab({ shift: true })
    expect(screen.getByText('Last')).toHaveFocus()
  })

  it('calls onEscape and restores focus to the trigger on deactivate', async () => {
    const user = userEvent.setup()
    const onEscape = vi.fn()
    render(<Harness onEscape={onEscape} />)
    await user.click(screen.getByText('Trigger'))
    await user.keyboard('{Escape}')

    expect(onEscape).toHaveBeenCalledOnce()
    expect(screen.getByText('Trigger')).toHaveFocus()
  })

  it('does not steal focus back to the first element when re-rendered with a new onEscape reference', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<Harness onEscape={() => {}} />)
    await user.click(screen.getByText('Trigger'))
    await user.tab()
    expect(screen.getByText('Last')).toHaveFocus()

    rerender(<Harness onEscape={() => {}} />)
    expect(screen.getByText('Last')).toHaveFocus()
  })
})
