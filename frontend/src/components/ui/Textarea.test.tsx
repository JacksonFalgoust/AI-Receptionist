import { createRef } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Textarea } from './Textarea'

describe('Textarea', () => {
  it('forwards a ref and accepts typed input', async () => {
    const ref = createRef<HTMLTextAreaElement>()
    const user = userEvent.setup()
    render(<Textarea ref={ref} aria-label="Notes" />)
    await user.type(screen.getByLabelText('Notes'), 'hello')
    expect(ref.current?.value).toBe('hello')
  })

  it('sets aria-invalid when invalid is true', () => {
    render(<Textarea aria-label="Notes" invalid />)
    expect(screen.getByLabelText('Notes')).toHaveAttribute('aria-invalid', 'true')
  })
})
