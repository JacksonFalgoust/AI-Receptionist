import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { DateScope } from './DateScope'

describe('DateScope', () => {
  it('offers the three MVP presets', () => {
    render(<DateScope value="today" onChange={() => {}} />)

    const options = screen.getAllByRole('radio').map((option) => option.getAttribute('value'))
    expect(options).toEqual(['today', '7d', '30d'])
  })

  it('marks the current scope as chosen, not by styling alone', () => {
    render(<DateScope value="7d" onChange={() => {}} />)

    expect(screen.getByRole('radio', { name: '7 days' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Today' })).not.toBeChecked()
  })

  it('reports the preset that was picked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<DateScope value="today" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: '30 days' }))

    expect(onChange).toHaveBeenCalledWith('30d')
  })

  it('moves between presets with arrow keys, as a radio group should', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<DateScope value="today" onChange={onChange} />)

    await user.tab()
    await user.keyboard('{ArrowRight}')

    expect(onChange).toHaveBeenCalledWith('7d')
  })

  it('names the group so a screen reader says what is being scoped', () => {
    render(<DateScope value="today" onChange={() => {}} />)

    expect(screen.getByRole('radiogroup', { name: 'Date scope' })).toBeInTheDocument()
  })
})
