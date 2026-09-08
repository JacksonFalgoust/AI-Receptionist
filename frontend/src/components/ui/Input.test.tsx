import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Input } from './Input'

describe('Input', () => {
  it('forwards a ref and accepts typed input', async () => {
    const ref = createRef<HTMLInputElement>()
    const user = userEvent.setup()
    render(<Input ref={ref} aria-label="Email" />)
    await user.type(screen.getByLabelText('Email'), 'a@b.com')
    expect(ref.current?.value).toBe('a@b.com')
  })

  it('sets aria-invalid when invalid is true', () => {
    render(<Input aria-label="Email" invalid />)
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
  })

  it('calls onChange on every keystroke, matching a native input', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Input aria-label="Email" onChange={onChange} />)
    await user.type(screen.getByLabelText('Email'), 'ab')
    expect(onChange).toHaveBeenCalledTimes(2)
  })
})
