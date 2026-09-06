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
})
