import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { AnalyticsPage } from './AnalyticsPage'

describe('AnalyticsPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<AnalyticsPage />)

    expect(screen.getByRole('heading', { name: 'Analytics' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByText('Total conversations')).toBeInTheDocument()
  })

  it('opens on 30 days, because a single day is a poor window for review', () => {
    renderWithProviders(<AnalyticsPage />)

    expect(screen.getByRole('radio', { name: '30 days' })).toBeChecked()
  })

  it('shows both the metrics and the intents table', async () => {
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByRole('region', { name: 'Performance metrics' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Top customer intents' })).toBeInTheDocument()
  })

  it('narrows every figure on the page when the scope changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByText('70')).toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: 'Today' }))

    expect(await screen.findByText('14')).toBeInTheDocument()
    expect(screen.queryByText('70')).not.toBeInTheDocument()
  })

  it('offers no Export and no conversion rate (US-4.1)', async () => {
    renderWithProviders(<AnalyticsPage />)

    await screen.findByText('Total conversations')
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/conversion rate/i)).not.toBeInTheDocument()
  })
})
