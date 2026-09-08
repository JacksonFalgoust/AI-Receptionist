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

function StackedHarness({
  onEscapeA,
  onEscapeB,
}: {
  onEscapeA: () => void
  onEscapeB: () => void
}) {
  const containerARef = useRef<HTMLDivElement>(null)
  const containerBRef = useRef<HTMLDivElement>(null)
  const [activeA, setActiveA] = useState(false)
  const [activeB, setActiveB] = useState(false)

  useFocusTrap(containerARef, activeA, onEscapeA)
  useFocusTrap(containerBRef, activeB, onEscapeB)

  return (
    <div>
      <button onClick={() => setActiveA(true)}>Trigger A</button>
      <button onClick={() => setActiveB(true)}>Trigger B</button>
      {activeA ? (
        <div ref={containerARef} tabIndex={-1}>
          <button>A First</button>
        </div>
      ) : null}
      {activeB ? (
        <div ref={containerBRef} tabIndex={-1}>
          <button>B First</button>
        </div>
      ) : null}
    </div>
  )
}

describe('useFocusTrap stacked overlays', () => {
  it('only invokes the topmost (most recently activated) trap on Escape', async () => {
    const user = userEvent.setup()
    const onEscapeA = vi.fn()
    const onEscapeB = vi.fn()
    render(<StackedHarness onEscapeA={onEscapeA} onEscapeB={onEscapeB} />)

    // Activate trap A first (e.g. a Drawer opens)...
    await user.click(screen.getByText('Trigger A'))
    expect(screen.getByText('A First')).toHaveFocus()

    // ...then trap B activates on top of it (e.g. a ConfirmDialog opened via
    // useConfirm() while the Drawer is still open).
    await user.click(screen.getByText('Trigger B'))
    expect(screen.getByText('B First')).toHaveFocus()

    await user.keyboard('{Escape}')

    expect(onEscapeB).toHaveBeenCalledOnce()
    expect(onEscapeA).not.toHaveBeenCalled()
  })
})
