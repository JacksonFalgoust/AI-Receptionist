import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Checkbox } from './Checkbox'

describe('Checkbox', () => {
  it('associates its visible label with the input', () => {
    render(<Checkbox label="Active" />)
    expect(screen.getByLabelText('Active')).toBeInTheDocument()
  })

  it('toggles checked state on click and calls onChange', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Checkbox label="Active" onChange={onChange} />)
    const box = screen.getByLabelText('Active')
    expect(box).not.toBeChecked()
    await user.click(box)
    expect(box).toBeChecked()
    expect(onChange).toHaveBeenCalledOnce()
  })
})
