import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Radio } from './Radio'

describe('Radio', () => {
  it('associates its visible label and only allows one selection per name group', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <Radio name="tone" label="Professional" value="professional" />
        <Radio name="tone" label="Friendly" value="friendly" />
      </div>,
    )
    await user.click(screen.getByLabelText('Professional'))
    expect(screen.getByLabelText('Professional')).toBeChecked()
    await user.click(screen.getByLabelText('Friendly'))
    expect(screen.getByLabelText('Friendly')).toBeChecked()
    expect(screen.getByLabelText('Professional')).not.toBeChecked()
  })
})
