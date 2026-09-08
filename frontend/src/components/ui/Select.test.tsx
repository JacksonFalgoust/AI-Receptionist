import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Select } from './Select'

const options = [
  { value: 'voice', label: 'Voice' },
  { value: 'sms', label: 'SMS' },
  { value: 'web', label: 'Web', disabled: true },
]

describe('Select', () => {
  it('renders a placeholder option plus one option per entry, forwarding a ref', () => {
    const ref = createRef<HTMLSelectElement>()
    render(<Select ref={ref} aria-label="Channel" options={options} placeholder="Choose a channel" />)
    const select = screen.getByLabelText('Channel')
    expect(select).toBe(ref.current)
    expect(screen.getByRole('option', { name: 'Choose a channel' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Voice' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Web' })).toBeDisabled()
  })

  it('calls onChange with the selected value', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<Select aria-label="Channel" options={options} onChange={onChange} />)
    await user.selectOptions(screen.getByLabelText('Channel'), 'sms')
    expect(onChange).toHaveBeenCalled()
    expect(screen.getByLabelText('Channel')).toHaveValue('sms')
  })

  it('sets aria-invalid when invalid is true', () => {
    render(<Select aria-label="Channel" options={options} invalid />)
    expect(screen.getByLabelText('Channel')).toHaveAttribute('aria-invalid', 'true')
  })
})
