import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { App } from './App'

describe('App', () => {
  it('mounts ToastProvider around the route tree', () => {
    render(<App />)
    expect(screen.getByTestId('toast-stack')).toBeInTheDocument()
  })

  it('still renders the login screen for an unauthenticated visitor', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /concierge/i })).toBeInTheDocument()
  })
})
