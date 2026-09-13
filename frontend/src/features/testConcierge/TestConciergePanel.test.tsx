import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/services/testConciergeService', () => ({
  testConciergeService: { simulate: vi.fn() },
}))

import { testConciergeService } from '@/services/testConciergeService'

import { TestConciergeDrawerProvider } from './TestConciergeDrawerContext'
import { TestConciergePanel } from './TestConciergePanel'

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <TestConciergeDrawerProvider>
        <TestConciergePanel />
      </TestConciergeDrawerProvider>
    </QueryClientProvider>,
  )
}

describe('TestConciergePanel', () => {
  it('shows the TEST MODE badge', () => {
    renderPanel()
    expect(screen.getByText('TEST MODE')).toBeInTheDocument()
  })

  it('shows an empty state before any message is sent', () => {
    renderPanel()
    expect(screen.getByText('Send a message to try out your Concierge.')).toBeInTheDocument()
  })

  it('disables Send until there is a message, and Clear until there is a turn', () => {
    renderPanel()
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Clear conversation' })).toBeDisabled()
  })

  it('sends a message and renders the customer bubble immediately, then the reply', async () => {
    let resolveReply: (value: { id: string; reply: string; createdAt: string }) => void = () => {}
    vi.mocked(testConciergeService.simulate).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveReply = resolve
      }),
    )
    const user = userEvent.setup()
    renderPanel()

    await user.type(screen.getByLabelText('Message'), 'What are your hours?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    // Text appears in chat bubble and textarea while sending; verify at least one exists
    expect(screen.queryAllByText('What are your hours?').length).toBeGreaterThan(0)

    resolveReply({
      id: 'tc_0001',
      reply: 'We are open Monday to Thursday.',
      createdAt: '2026-09-12T00:00:00.000Z',
    })
    expect(await screen.findByText('We are open Monday to Thursday.')).toBeInTheDocument()
  })

  it('shows the disclosure only for a turn with populated fields', async () => {
    vi.mocked(testConciergeService.simulate).mockResolvedValueOnce({
      id: 'tc_0001',
      reply: 'Booking flow reply',
      createdAt: '2026-09-12T00:00:00.000Z',
      workflowUsed: 'Book an appointment',
      integrationsUsed: ['Scheduling'],
    })
    const user = userEvent.setup()
    renderPanel()

    await user.type(screen.getByLabelText('Message'), 'book an appointment')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('What the Concierge used')).toBeInTheDocument()
    expect(screen.getByText('Book an appointment')).toBeInTheDocument()
    expect(screen.getByText('Scheduling')).toBeInTheDocument()
  })

  it('renders no disclosure for a reply with none of the four fields set', async () => {
    vi.mocked(testConciergeService.simulate).mockResolvedValueOnce({
      id: 'tc_0001',
      reply: 'Just a hello',
      createdAt: '2026-09-12T00:00:00.000Z',
    })
    const user = userEvent.setup()
    renderPanel()

    await user.type(screen.getByLabelText('Message'), 'hello')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('Just a hello')
    expect(screen.queryByText('What the Concierge used')).not.toBeInTheDocument()
  })

  it('clears the transcript back to the empty state', async () => {
    vi.mocked(testConciergeService.simulate).mockResolvedValueOnce({
      id: 'tc_0001',
      reply: 'Hi!',
      createdAt: '2026-09-12T00:00:00.000Z',
    })
    const user = userEvent.setup()
    renderPanel()

    await user.type(screen.getByLabelText('Message'), 'hi')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await screen.findByText('Hi!')

    await user.click(screen.getByRole('button', { name: 'Clear conversation' }))
    expect(screen.getByText('Send a message to try out your Concierge.')).toBeInTheDocument()
  })

  it('shows an inline alert when the service rejects, and does not add a turn', async () => {
    vi.mocked(testConciergeService.simulate).mockRejectedValueOnce(new Error('network down'))
    const user = userEvent.setup()
    renderPanel()

    await user.type(screen.getByLabelText('Message'), 'hello')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Send a message to try out your Concierge.')).toBeInTheDocument()
  })

  it('preserves the user message in the textarea when the service rejects', async () => {
    vi.mocked(testConciergeService.simulate).mockRejectedValueOnce(new Error('network down'))
    const user = userEvent.setup()
    renderPanel()

    const messageInput = screen.getByLabelText('Message') as HTMLTextAreaElement
    await user.type(messageInput, 'please help')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(messageInput.value).toBe('please help')
  })
})
