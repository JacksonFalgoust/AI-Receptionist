import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { AppError } from '@/services/errors'

import { ErrorState } from './ErrorState'

function renderInRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('ErrorState', () => {
  it('renders the AppError title and description', () => {
    const error = new AppError({
      kind: 'server',
      title: 'Reservation system unavailable',
      description: 'Concierge was unable to connect to the reservation system.',
    })
    renderInRouter(<ErrorState error={error} />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Reservation system unavailable')).toBeInTheDocument()
    expect(
      screen.getByText('Concierge was unable to connect to the reservation system.'),
    ).toBeInTheDocument()
  })

  it('normalises a non-AppError into human-readable copy', () => {
    renderInRouter(<ErrorState error={new Error('API_ERROR_451')} />)

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.queryByText(/API_ERROR_451/)).not.toBeInTheDocument()
  })

  it('wires a retry action to onRetry', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    const error = new AppError({
      kind: 'network',
      title: 'Cannot reach GuideAnts Concierge',
      description: 'Check your network connection.',
      actions: [{ label: 'Retry', retry: true }],
    })
    renderInRouter(<ErrorState error={error} onRetry={onRetry} />)

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('omits the retry action when no onRetry is supplied', () => {
    const error = new AppError({
      kind: 'network',
      title: 'Cannot reach GuideAnts Concierge',
      description: 'Check your network connection.',
      actions: [{ label: 'Retry', retry: true }],
    })
    renderInRouter(<ErrorState error={error} />)

    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('renders an href action as a link', () => {
    const error = new AppError({
      kind: 'server',
      title: 'Reservation system unavailable',
      description: 'Check the integration or try again.',
      actions: [{ label: 'View integration', href: '/integrations' }],
    })
    renderInRouter(<ErrorState error={error} />)

    expect(screen.getByRole('link', { name: 'View integration' })).toHaveAttribute(
      'href',
      '/integrations',
    )
  })
})
