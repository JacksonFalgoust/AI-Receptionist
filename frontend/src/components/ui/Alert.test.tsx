import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Alert } from './Alert'

describe('Alert', () => {
  it('renders as an alert role with title and description', () => {
    render(
      <Alert
        tone="danger"
        title="Reservation system unavailable"
        description="Try again in a few minutes."
      />,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Reservation system unavailable')
    expect(alert).toHaveTextContent('Try again in a few minutes.')
  })

  it('renders an action button that calls its handler', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(
      <Alert
        tone="danger"
        title="Reservation system unavailable"
        actions={[{ label: 'Retry', onClick: onRetry }]}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
