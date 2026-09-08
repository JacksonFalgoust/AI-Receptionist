import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Toggle } from './Toggle'

describe('Toggle', () => {
  it('exposes a switch role with its label as the accessible name', () => {
    render(<Toggle label="Enable payments" />)
    expect(screen.getByRole('switch', { name: 'Enable payments' })).toBeInTheDocument()
  })

  it('flips checked state on click', async () => {
    const user = userEvent.setup()
    render(<Toggle label="Enable payments" />)
    const toggle = screen.getByRole('switch', { name: 'Enable payments' })
    expect(toggle).not.toBeChecked()
    await user.click(toggle)
    expect(toggle).toBeChecked()
  })
})
