import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { AnalyticsKpiRow } from './AnalyticsKpiRow'
import { TopIntentsTable } from './TopIntentsTable'

describe('AnalyticsKpiRow', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('shows exactly the three metrics US-4.1 allows', async () => {
    renderWithProviders(<AnalyticsKpiRow range={{ preset: '30d' }} />)

    expect(await screen.findByText('Total conversations')).toBeInTheDocument()
    expect(screen.getByText('Escalation rate')).toBeInTheDocument()
    expect(screen.getByText('Avg duration')).toBeInTheDocument()
    expect(screen.queryByText(/conversion rate/i)).not.toBeInTheDocument()
  })

  it('reads a rate as a percentage and a duration in minutes', async () => {
    renderWithProviders(<AnalyticsKpiRow range={{ preset: '30d' }} />)

    // 70 seeded conversations, 14 escalated; durations average 303 seconds.
    expect(await screen.findByText('70')).toBeInTheDocument()
    expect(screen.getByText('20%')).toBeInTheDocument()
    expect(screen.getByText('5m 03s')).toBeInTheDocument()
  })

  it('narrows to the range it is given', async () => {
    renderWithProviders(<AnalyticsKpiRow range={{ preset: 'today' }} />)

    // The 14 conversations seeded within the last ~19 hours are the only
    // ones that could ever fall in "today" (since midnight, not a rolling
    // 24h window) -- the other 56 are all seeded 31+ hours in the past.
    // Asserting a range rather than an exact count keeps this independent
    // of what wall-clock hour the suite happens to run at: how many of
    // those 14 have actually happened since the most recent midnight
    // depends on the time of day, from 0 (just after midnight) up to all
    // 14 (just before the next one).
    const label = await screen.findByText('Total conversations')
    const today = Number(label.nextElementSibling!.textContent)
    expect(today).toBeGreaterThanOrEqual(0)
    expect(today).toBeLessThanOrEqual(14)
  })

  it('reports zero rather than nothing when a range contains no conversations', async () => {
    store.conversations.length = 0
    renderWithProviders(<AnalyticsKpiRow range={{ preset: '30d' }} />)

    expect(await screen.findByText('Total conversations')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
  })
})

describe('TopIntentsTable', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('lists intents by volume, with no trend column', async () => {
    renderWithProviders(<TopIntentsTable range={{ preset: '30d' }} />)

    await screen.findByText('Book appointment')
    expect(screen.getAllByRole('columnheader').map((header) => header.textContent?.trim())).toEqual([
      'Intent',
      'Volume',
    ])
  })

  it('orders the busiest intent first', async () => {
    renderWithProviders(<TopIntentsTable range={{ preset: '30d' }} />)

    await screen.findByText('Book appointment')
    const rows = screen.getAllByRole('row').slice(1)
    const volumes = rows.map((row) => Number(row.querySelectorAll('td')[1].textContent))
    expect([...volumes].sort((a, b) => b - a)).toEqual(volumes)
  })

  it('says so when a range produced no intents at all', async () => {
    store.conversations.length = 0
    renderWithProviders(<TopIntentsTable range={{ preset: '30d' }} />)

    expect(await screen.findByText('No intents recorded yet')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
