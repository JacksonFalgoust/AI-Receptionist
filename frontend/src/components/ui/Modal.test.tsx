import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Modal } from './Modal'

describe('Modal', () => {
  it('renders nothing when closed', () => {
    render(
      <Modal isOpen={false} onClose={vi.fn()} title="Delete workflow?">
        Are you sure?
      </Modal>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders the dialog with its title and content when open', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Delete workflow?">
        Are you sure?
      </Modal>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Delete workflow?' })
    expect(dialog).toHaveTextContent('Are you sure?')
  })

  it('calls onClose on Escape', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <Modal isOpen onClose={onClose} title="Delete workflow?">
        Are you sure?
      </Modal>,
    )
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when the backdrop is clicked, but not when the dialog itself is clicked', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <Modal isOpen onClose={onClose} title="Delete workflow?">
        Are you sure?
      </Modal>,
    )
    await user.click(screen.getByText('Are you sure?'))
    expect(onClose).not.toHaveBeenCalled()

    await user.click(screen.getByRole('dialog').parentElement as HTMLElement)
    expect(onClose).toHaveBeenCalledOnce()
  })
})
