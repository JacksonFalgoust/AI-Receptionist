import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/services/testConciergeService', () => ({
  testConciergeService: { simulate: vi.fn() },
}))

import { testConciergeService } from '@/services/testConciergeService'

import { TestConciergeDrawerProvider } from './TestConciergeDrawerContext'
import { useTestConciergeDrawer } from './useTestConciergeDrawer'

function Harness() {
  const drawer = useTestConciergeDrawer()
  return (
    <div>
      <p>isOpen: {String(drawer.isOpen)}</p>
      <p>turns: {drawer.turns.length}</p>
      <p>pending: {drawer.pendingMessage ?? 'none'}</p>
      <button onClick={drawer.open}>Open</button>
      <button onClick={drawer.close}>Close</button>
      <button onClick={drawer.clear}>Clear</button>
      <button
        onClick={() => {
          void drawer.send('hello').catch(() => {})
        }}
      >
        Send
      </button>
    </div>
  )
}

function renderHarness() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <TestConciergeDrawerProvider>
        <Harness />
      </TestConciergeDrawerProvider>
    </QueryClientProvider>,
  )
}

describe('TestConciergeDrawerProvider / useTestConciergeDrawer', () => {
  it('starts closed with an empty transcript', () => {
    renderHarness()
    expect(screen.getByText('isOpen: false')).toBeInTheDocument()
    expect(screen.getByText('turns: 0')).toBeInTheDocument()
  })

  it('opens and closes', async () => {
    const user = userEvent.setup()
    renderHarness()

    await user.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByText('isOpen: true')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.getByText('isOpen: false')).toBeInTheDocument()
  })

  it('appends a turn pairing the sent message with the resolved reply', async () => {
    vi.mocked(testConciergeService.simulate).mockResolvedValueOnce({
      id: 'tc_0001',
      reply: 'Hi there!',
      createdAt: '2026-09-12T00:00:00.000Z',
    })
    const user = userEvent.setup()
    renderHarness()

    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('turns: 1')).toBeInTheDocument())
    expect(screen.getByText('pending: none')).toBeInTheDocument()
  })

  it('clears the transcript', async () => {
    vi.mocked(testConciergeService.simulate).mockResolvedValueOnce({
      id: 'tc_0001',
      reply: 'Hi there!',
      createdAt: '2026-09-12T00:00:00.000Z',
    })
    const user = userEvent.setup()
    renderHarness()

    await user.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(screen.getByText('turns: 1')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(screen.getByText('turns: 0')).toBeInTheDocument()
  })

  it('leaves turns unchanged and clears pendingMessage when the service rejects', async () => {
    vi.mocked(testConciergeService.simulate).mockRejectedValueOnce(new Error('boom'))
    const user = userEvent.setup()
    renderHarness()

    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('pending: none')).toBeInTheDocument())
    expect(screen.getByText('turns: 0')).toBeInTheDocument()
  })
})
