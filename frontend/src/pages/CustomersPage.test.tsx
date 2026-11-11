import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { customerService } from '@/services/customerService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { CustomersPage } from './CustomersPage'

describe('CustomersPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    resetStore()
    seedSession()
  })

  it('lists every customer', async () => {
    renderWithProviders(<CustomersPage />)
    expect(screen.getByRole('heading', { name: 'Customers' })).toBeInTheDocument()
    expect(await screen.findByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.getByText('Tom Okafor')).toBeInTheDocument()
  })

  it('filters by search term', async () => {
    const user = userEvent.setup()
    renderWithProviders(<CustomersPage />)
    await screen.findByText('Dana Whitfield')
    await user.type(screen.getByLabelText('Search customers'), 'elena')
    expect(await screen.findByText('Elena Rossi')).toBeInTheDocument()
    await vi.waitFor(() => expect(screen.queryByText('Dana Whitfield')).not.toBeInTheDocument())
  })

  it('shows an error state when Booqable is unreachable', async () => {
    vi.spyOn(customerService, 'list').mockRejectedValue(
      new AppError({ kind: 'server', title: "Couldn't reach Booqable", description: 'Try again.' }),
    )
    renderWithProviders(<CustomersPage />)
    expect(await screen.findByText("Couldn't reach Booqable")).toBeInTheDocument()
  })
})
