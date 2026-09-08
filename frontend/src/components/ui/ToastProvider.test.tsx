import { describe, expect, it, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'

import { ToastProvider, useToast } from './ToastProvider'

function Harness() {
  const { show } = useToast()
  return (
    <div>
      <button onClick={() => show('Saved', { tone: 'success' })}>Save</button>
      <button onClick={() => show('Could not save', { tone: 'danger' })}>Fail</button>
    </div>
  )
}

describe('ToastProvider / useToast', () => {
  it('renders its toast-stack container even with nothing to show', () => {
    render(
      <ToastProvider>
        <p>app content</p>
      </ToastProvider>,
    )
    expect(screen.getByTestId('toast-stack')).toBeInTheDocument()
  })

  it('shows a toast and auto-dismisses a success toast after its duration', async () => {
    vi.useFakeTimers()
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByRole('status')).toHaveTextContent('Saved')

    await act(() => {
      vi.advanceTimersByTime(4000)
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('keeps a danger toast visible past the success duration until dismissed', async () => {
    vi.useFakeTimers()
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Fail' }))
    await act(() => {
      vi.advanceTimersByTime(10_000)
    })
    expect(screen.getByRole('status')).toHaveTextContent('Could not save')

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('cancels the pending auto-dismiss timer when a success toast is dismissed manually first', async () => {
    vi.useFakeTimers()
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(vi.getTimerCount()).toBe(1)

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(vi.getTimerCount()).toBe(0)
    vi.useRealTimers()
  })

  it('throws if useToast is called outside a ToastProvider', () => {
    function Bare() {
      useToast()
      return null
    }
    expect(() => render(<Bare />)).toThrow('useToast must be used within a ToastProvider')
  })
})
