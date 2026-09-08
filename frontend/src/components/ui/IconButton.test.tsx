import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { X } from 'lucide-react'

import { IconButton } from './IconButton'

describe('IconButton', () => {
  it('exposes its accessible name via the required aria-label', () => {
    render(<IconButton icon={<X />} aria-label="Close" />)
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<IconButton icon={<X />} aria-label="Close" onClick={onClick} />)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})
