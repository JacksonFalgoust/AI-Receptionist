import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Table } from '@/components/ui/Table'
import type { Booking } from '@/types'

import { BOOKING_COLUMNS, formatRenting } from './bookingColumns'

const BOOKING: Booking = {
  id: 'bk_1',
  number: 1001,
  label: null,
  customerName: null,
  customerPhone: null,
  customerEmail: null,
  items: null,
  itemCount: null,
  startsAt: '2026-11-10T15:00:00Z',
  stopsAt: '2026-11-10T19:00:00Z',
  totalCents: 12000,
  payment: 'paid',
  booqableUrl: 'https://example.booqable.com/orders/bk_1',
}

function renderRow(overrides: Partial<Booking> = {}) {
  return render(
    <Table
      columns={BOOKING_COLUMNS}
      rows={[{ ...BOOKING, ...overrides }]}
      getRowId={(b) => b.id}
      frame={false}
    />,
  )
}

describe('formatRenting', () => {
  it('lists quantities and names', () => {
    expect(
      formatRenting(
        [
          { name: 'Kayak', quantity: 2 },
          { name: 'Paddleboard', quantity: 1 },
        ],
        3,
      ),
    ).toBe('2 × Kayak, 1 × Paddleboard')
  })

  it('falls back to a count when the lines are unknown', () => {
    expect(formatRenting(null, 3)).toBe('3 items')
    expect(formatRenting([], 1)).toBe('1 item')
  })

  it('shows a dash when nothing is known', () => {
    expect(formatRenting(null, null)).toBe('—')
    expect(formatRenting([], 0)).toBe('—')
  })

  it('names a nameless line Item', () => {
    expect(formatRenting([{ name: null, quantity: 1 }], 1)).toBe('1 × Item')
  })
})

describe('BOOKING_COLUMNS', () => {
  it('shows No customer and no contact line without customer details', () => {
    renderRow()
    expect(screen.getByText('No customer')).toBeInTheDocument()
    const cell = screen.getByText('No customer').closest('td')!
    expect(cell.querySelectorAll('p, div > div')).toHaveLength(0)
    expect(cell).toHaveTextContent(/^No customer$/)
  })

  it('shows the phone, else the email, beneath the name', () => {
    renderRow({ customerName: 'Dana', customerPhone: '+1555', customerEmail: 'd@x.com' })
    expect(screen.getByText('+1555')).toBeInTheDocument()
    expect(screen.queryByText('d@x.com')).not.toBeInTheDocument()
  })

  it('links to Booqable in a new tab', () => {
    renderRow()
    const link = screen.getByRole('link', { name: 'Open in Booqable' })
    expect(link).toHaveAttribute('href', BOOKING.booqableUrl)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noreferrer')
  })

  it('leaves the status cell empty when there is no label', () => {
    renderRow({ label: null })
    expect(screen.queryByText('Out now')).not.toBeInTheDocument()
    const index = BOOKING_COLUMNS.findIndex((c) => c.id === 'status')
    const cells = screen.getAllByRole('cell')
    expect(cells[index]).toBeEmptyDOMElement()
  })

  it('shows the label when set', () => {
    renderRow({ label: 'out_now' })
    expect(screen.getByText('Out now')).toBeInTheDocument()
  })
})
