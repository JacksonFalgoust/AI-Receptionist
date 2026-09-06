import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { Breadcrumb } from './Breadcrumb'

describe('Breadcrumb', () => {
  it('renders every item as a link except the current (last) one', () => {
    render(
      <MemoryRouter>
        <Breadcrumb
          items={[
            { label: 'Conversations', href: '/conversations' },
            { label: 'Call with Dana Ortiz' },
          ]}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Conversations' })).toHaveAttribute(
      'href',
      '/conversations',
    )
    const current = screen.getByText('Call with Dana Ortiz')
    expect(current.tagName).not.toBe('A')
    expect(current).toHaveAttribute('aria-current', 'page')
  })

  it('never renders the last item as a link, even when it has an href', () => {
    render(
      <MemoryRouter>
        <Breadcrumb
          items={[
            { label: 'Conversations', href: '/conversations' },
            { label: 'Call with Dana Ortiz', href: '/conversations/123' },
          ]}
        />
      </MemoryRouter>,
    )
    const current = screen.getByText('Call with Dana Ortiz')
    expect(current.tagName).not.toBe('A')
    expect(current).toHaveAttribute('aria-current', 'page')
    expect(screen.getAllByRole('link')).toHaveLength(1)
  })
})
