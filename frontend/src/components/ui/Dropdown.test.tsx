import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Dropdown } from './Dropdown'

describe('Dropdown', () => {
  it('opens the menu on trigger click and closes it on a second click', async () => {
    const user = userEvent.setup()
    render(
      <Dropdown trigger={<button>Options</button>}>
        <div>Menu content</div>
      </Dropdown>,
    )
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Options' }))
    expect(screen.getByRole('menu')).toHaveTextContent('Menu content')

    await user.click(screen.getByRole('button', { name: 'Options' }))
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('closes on an outside click', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <Dropdown trigger={<button>Options</button>}>
          <div>Menu content</div>
        </Dropdown>
        <button>Elsewhere</button>
      </div>,
    )
    await user.click(screen.getByRole('button', { name: 'Options' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Elsewhere' }))
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    render(
      <Dropdown trigger={<button>Options</button>}>
        <div>Menu content</div>
      </Dropdown>,
    )
    await user.click(screen.getByRole('button', { name: 'Options' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('when a nested dropdown opens on top of an outer one, Escape only closes the topmost one', async () => {
    const user = userEvent.setup()
    render(
      <Dropdown trigger={<button>Outer</button>}>
        <Dropdown trigger={<button>Inner</button>}>
          <div>Inner menu</div>
        </Dropdown>
      </Dropdown>,
    )

    // Open the outer dropdown, then the inner one nested inside it (stacked,
    // inner registered after the outer — clicking "Inner" is inside the
    // outer's root, so it doesn't trigger the outer's outside-click close).
    await user.click(screen.getByRole('button', { name: 'Outer' }))
    await user.click(screen.getByRole('button', { name: 'Inner' }))
    expect(screen.getAllByRole('menu')).toHaveLength(2)

    await user.keyboard('{Escape}')

    // Only the topmost (inner) dropdown closes; the outer one remains open.
    expect(screen.queryByText('Inner menu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Inner' })).toBeInTheDocument()
  })

  it('marks the trigger with haspopup and reflects the open state', async () => {
    const user = userEvent.setup()
    render(
      <Dropdown trigger={<button type="button">Open</button>}>
        <p>Panel</p>
      </Dropdown>,
    )

    const trigger = screen.getByRole('button', { name: 'Open' })
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  it('renders as a dialog with an accessible name when asked', async () => {
    const user = userEvent.setup()
    render(
      <Dropdown role="dialog" label="Concierge status" trigger={<button type="button">Status</button>}>
        <p>Concierge is active</p>
      </Dropdown>,
    )

    const trigger = screen.getByRole('button', { name: 'Status' })
    expect(trigger).toHaveAttribute('aria-haspopup', 'dialog')

    await user.click(trigger)

    expect(screen.getByRole('dialog', { name: 'Concierge status' })).toBeInTheDocument()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
