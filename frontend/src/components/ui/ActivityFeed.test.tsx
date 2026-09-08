import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { ActivityFeed } from './ActivityFeed'

describe('ActivityFeed', () => {
  it('renders the empty state when there are no items', () => {
    render(
      <MemoryRouter>
        <ActivityFeed items={[]} />
      </MemoryRouter>,
    )
    expect(screen.getByText('No recent activity')).toBeInTheDocument()
  })

  it('renders each item with its status pill and links through when href is given', () => {
    render(
      <MemoryRouter>
        <ActivityFeed
          items={[
            {
              id: '1',
              time: '9:41 AM',
              type: 'Reservation booked',
              context: 'Dana Ortiz',
              channel: 'Voice',
              status: 'resolved',
              href: '/conversations/1',
            },
          ]}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('Reservation booked')).toBeInTheDocument()
    expect(screen.getByText('Resolved')).toBeInTheDocument()
    expect(screen.getByText('Dana Ortiz · Voice · 9:41 AM')).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/conversations/1')
  })

  it('renders an item without href as plain content, not wrapped in a link', () => {
    render(
      <MemoryRouter>
        <ActivityFeed
          items={[
            {
              id: '2',
              time: '9:52 AM',
              type: 'Escalated to human',
              context: 'Marcus Chen',
              channel: 'SMS',
              status: 'new',
            },
          ]}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('Escalated to human')).toBeInTheDocument()
    expect(screen.getByText('Marcus Chen · SMS · 9:52 AM')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
