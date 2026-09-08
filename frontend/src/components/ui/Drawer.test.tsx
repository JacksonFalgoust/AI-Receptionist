import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Drawer } from './Drawer'

describe('Drawer', () => {
  it('renders nothing when closed', () => {
    render(
      <Drawer isOpen={false} onClose={vi.fn()} title="Test Concierge">
        content
      </Drawer>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders the dialog with title, content, and footer when open', () => {
    render(
      <Drawer isOpen onClose={vi.fn()} title="Test Concierge" footer={<button>Close</button>}>
        content
      </Drawer>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Test Concierge' })
    expect(dialog).toHaveTextContent('content')
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('calls onClose on Escape and on backdrop click', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <Drawer isOpen onClose={onClose} title="Test Concierge">
        content
      </Drawer>,
    )
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('dialog').parentElement as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('does not call onClose when the drawer content itself is clicked', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <Drawer isOpen onClose={onClose} title="Test Concierge">
        content
      </Drawer>,
    )
    await user.click(screen.getByText('content'))
    expect(onClose).not.toHaveBeenCalled()
  })
})
