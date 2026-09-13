import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { BillingPage } from './BillingPage'

describe('BillingPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('shows the plan summary once loaded', async () => {
    renderWithProviders(<BillingPage />)
    expect(await screen.findByText('Concierge Professional')).toBeInTheDocument()
    expect(screen.getByText('Visa ending 4242')).toBeInTheDocument()
  })

  it('shows a meter for each of the four usage metrics', async () => {
    renderWithProviders(<BillingPage />)
    await screen.findByText('Concierge Professional')

    expect(screen.getAllByRole('meter')).toHaveLength(4)
    expect(screen.getByRole('meter', { name: 'Voice minutes' })).toBeInTheDocument()
    expect(screen.getByText('80% — approaching your plan limit')).toBeInTheDocument()
  })

  it('lists the seeded invoices', async () => {
    renderWithProviders(<BillingPage />)
    expect(await screen.findByText('HP-2026-0003')).toBeInTheDocument()
    expect(screen.getByText('HP-2026-0001')).toBeInTheDocument()
  })
})
