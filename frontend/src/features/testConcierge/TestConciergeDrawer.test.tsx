import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { TestConciergeDrawer } from './TestConciergeDrawer'
import { TestConciergeDrawerContext } from './TestConciergeDrawerContext'
import type { TestConciergeDrawerContextValue } from './TestConciergeDrawerContext'

function renderDrawer(overrides: Partial<TestConciergeDrawerContextValue> = {}) {
  const value: TestConciergeDrawerContextValue = {
    isOpen: true,
    open: vi.fn(),
    close: vi.fn(),
    turns: [],
    pendingMessage: null,
    isSending: false,
    send: vi.fn().mockResolvedValue(undefined),
    clear: vi.fn(),
    ...overrides,
  }
  const queryClient = new QueryClient()
  return {
    value,
    ...render(
      <QueryClientProvider client={queryClient}>
        <TestConciergeDrawerContext.Provider value={value}>
          <TestConciergeDrawer />
        </TestConciergeDrawerContext.Provider>
      </QueryClientProvider>,
    ),
  }
}

describe('TestConciergeDrawer', () => {
  it('renders as a dialog titled "Test Concierge" when open', () => {
    renderDrawer()
    expect(screen.getByRole('dialog', { name: 'Test Concierge' })).toBeInTheDocument()
  })

  it('renders nothing when closed', () => {
    renderDrawer({ isOpen: false })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('calls close on Escape', async () => {
    const user = userEvent.setup()
    const { value } = renderDrawer()

    await user.keyboard('{Escape}')
    expect(value.close).toHaveBeenCalledTimes(1)
  })
})
