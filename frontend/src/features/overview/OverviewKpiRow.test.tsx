import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { dashboardService } from '@/services/dashboardService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { OverviewKpiRow } from './OverviewKpiRow'

const KPI_LABELS = [
  'Conversations Today',
  'Calls Answered',
  'Requests Completed',
  'Human Escalations',
  'Transactions Created',
]

describe('OverviewKpiRow', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('renders exactly the five KPIs US-2.2 requires, in order', async () => {
    renderWithProviders(<OverviewKpiRow />)

    await screen.findByText(KPI_LABELS[0])
    const rendered = screen
      .getAllByRole('article')
      .map((card) => card.querySelector('p')?.textContent)

    expect(rendered).toEqual(KPI_LABELS)
  })

  it('shows the value the service computed for each KPI', async () => {
    const { kpis } = await dashboardService.getOverview({ preset: 'today' })
    renderWithProviders(<OverviewKpiRow />)

    for (const kpi of kpis) {
      const card = (await screen.findByText(kpi.label)).closest('article')
      expect(card).toHaveTextContent(String(kpi.value))
    }
  })

  it('scopes the query to the range it is given', async () => {
    const spy = vi.spyOn(dashboardService, 'getOverview')
    renderWithProviders(<OverviewKpiRow range={{ preset: '30d' }} />)

    await screen.findByText('Conversations Today')
    expect(spy).toHaveBeenCalledWith({ preset: '30d' })
  })

  it('counts a newly escalated conversation once the range widens', async () => {
    renderWithProviders(<OverviewKpiRow range={{ preset: '30d' }} />)

    const escalated = store.conversations.filter((item) => item.escalated).length
    const card = (await screen.findByText('Human Escalations')).closest('article')
    expect(card).toHaveTextContent(String(escalated))
  })

  it('holds the five-card shape while loading rather than one flat block', () => {
    renderWithProviders(<OverviewKpiRow />)

    expect(screen.getByRole('status', { name: 'Loading key metrics' })).toBeInTheDocument()
    expect(screen.queryByText('Conversations Today')).not.toBeInTheDocument()
  })

  it('shows a human-readable error with a retry when the metrics fail to load', async () => {
    const user = userEvent.setup()
    const spy = vi
      .spyOn(dashboardService, 'getOverview')
      .mockRejectedValue(
        new AppError({
          kind: 'network',
          title: 'Cannot reach GuideAnts Concierge',
          description: 'Check your network connection and try again.',
          actions: [{ label: 'Retry', retry: true }],
        }),
      )
    renderWithProviders(<OverviewKpiRow />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Check your network connection and try again.',
    )

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(spy.mock.calls.length).toBeGreaterThan(1)
  })

  it('formats a KPI by its declared format, not as a raw number', async () => {
    // Every Overview KPI is a plain count today, so this guards the row against
    // the day a rate or a duration is added to what the service returns.
    vi.spyOn(dashboardService, 'getOverview').mockResolvedValue({
      kpis: [
        { id: 'escalation_rate', label: 'Escalation rate', value: 20, format: 'percent' },
        { id: 'avg_duration', label: 'Avg duration', value: 303, format: 'duration' },
      ],
    })

    renderWithProviders(<OverviewKpiRow />)

    expect(await screen.findByText('20%')).toBeInTheDocument()
    expect(screen.getByText('5m 03s')).toBeInTheDocument()
  })
})
