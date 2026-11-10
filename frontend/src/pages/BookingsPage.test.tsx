import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'

import { resetStore } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { bookingService } from '@/services/bookingService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { BookingsPage } from './BookingsPage'

function Probe() {
  const location = useLocation()
  return <p data-testid="search">{location.search}</p>
}

describe('BookingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    resetStore()
    seedSession()
  })

  it('shows the heading and the four summary cards', async () => {
    renderWithProviders(<BookingsPage />)
    expect(screen.getByRole('heading', { name: 'Bookings' })).toBeInTheDocument()
    const summary = await screen.findByLabelText('Booking summary')
    for (const label of ['Pickups today', 'Returns today', 'Next 7 days', 'Unpaid']) {
      expect(summary).toHaveTextContent(label)
    }
    expect(summary).toHaveTextContent(/Pickups today\s*1/)
    expect(summary).toHaveTextContent(/Next 7 days\s*2/)
  })

  it('lists only upcoming bookings on the Upcoming tab', async () => {
    renderWithProviders(<BookingsPage />)
    expect(await screen.findByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.getByText('Tom Okafor')).toBeInTheDocument()
    expect(screen.queryByText('Elena Rossi')).not.toBeInTheDocument()
  })

  it('switches to Past and records the view in the URL', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <>
        <BookingsPage />
        <Probe />
      </>,
    )
    await screen.findByText('Dana Whitfield')
    await user.click(screen.getByRole('tab', { name: 'Past' }))

    expect(await screen.findByText('Returned')).toBeInTheDocument()
    expect(screen.getByText('Canceled')).toBeInTheDocument()
    expect(screen.getByText('Not picked up')).toBeInTheDocument()
    expect(screen.getByTestId('search')).toHaveTextContent('view=past')
  })

  it('bypasses the server cache exactly once per Refresh click', async () => {
    const user = userEvent.setup()
    const spy = vi.spyOn(bookingService, 'list')
    renderWithProviders(<BookingsPage />)
    await screen.findByText('Dana Whitfield')

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls[0][0]).toMatchObject({ refresh: false })

    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    expect(spy.mock.calls[1][0]).toMatchObject({ refresh: true })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh' })).toBeEnabled())
    expect(spy.mock.calls.filter(([p]) => p?.refresh === true)).toHaveLength(1)
  })

  it('shows the empty state for no upcoming bookings', async () => {
    const real = await bookingService.list()
    vi.spyOn(bookingService, 'list').mockResolvedValue({ ...real, items: [], total: 0 })
    renderWithProviders(<BookingsPage />)
    expect(await screen.findByText('No upcoming bookings')).toBeInTheDocument()
    expect(
      screen.getByText('New bookings from calls or your Booqable site will appear here.'),
    ).toBeInTheDocument()
  })

  it('shows the error title when Booqable cannot be reached', async () => {
    vi.spyOn(bookingService, 'list').mockRejectedValue(
      new AppError({
        kind: 'server',
        title: "Couldn't reach Booqable",
        description: 'Bookings are read live from Booqable. Try again in a moment.',
        actions: [{ label: 'Try again', retry: true }],
      }),
    )
    renderWithProviders(<BookingsPage />)
    expect(await screen.findByText("Couldn't reach Booqable")).toBeInTheDocument()
  })

  it('keeps the loading skeleton inside the panel', () => {
    renderWithProviders(<BookingsPage />)
    expect(screen.getByTestId('bookings-panel')).toContainElement(
      screen.getAllByRole('status').find((el) => !el.getAttribute('aria-label')?.includes('summary')) ??
        screen.getAllByRole('status')[0],
    )
  })
})
