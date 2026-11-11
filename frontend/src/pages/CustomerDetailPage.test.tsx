import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'

import { resetStore } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { CustomerDetailPage } from './CustomerDetailPage'

function renderAt(id: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/customers/:id" element={<CustomerDetailPage />} />
    </Routes>,
    { route: `/customers/${id}` },
  )
}

describe('CustomerDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    resetStore()
    seedSession()
  })

  it("shows the customer and their bookings", async () => {
    renderAt('cu_1')
    expect(await screen.findByRole('heading', { name: 'Dana Whitfield' })).toBeInTheDocument()
    expect(screen.getByText(/Bookings \(\d+\)/)).toBeInTheDocument()
    expect(screen.queryByText('Tom Okafor')).not.toBeInTheDocument()
  })

  it('shows not-found for an unknown customer', async () => {
    renderAt('nope')
    expect(await screen.findByText('Customer not found')).toBeInTheDocument()
  })
})
