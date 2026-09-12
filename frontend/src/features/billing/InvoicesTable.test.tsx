import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Invoice } from '@/types'

import { InvoicesTable } from './InvoicesTable'

const INVOICES: Invoice[] = [
  {
    id: 'inv_0003',
    number: 'HP-2026-0003',
    issuedAt: '2026-08-30T00:00:00.000Z',
    amountCents: 89900,
    currency: 'USD',
    status: 'due',
  },
  {
    id: 'inv_0002',
    number: 'HP-2026-0002',
    issuedAt: '2026-07-31T00:00:00.000Z',
    amountCents: 89900,
    currency: 'USD',
    status: 'paid',
  },
]

describe('InvoicesTable', () => {
  it('renders each invoice with its number, date, amount, and status', () => {
    render(<InvoicesTable invoices={INVOICES} periodEnd="2026-09-29T00:00:00.000Z" />)

    expect(screen.getByText('HP-2026-0003')).toBeInTheDocument()
    expect(screen.getByText('Aug 30, 2026')).toBeInTheDocument()
    expect(screen.getAllByText('$899.00')).toHaveLength(2)
    expect(screen.getByText('Due')).toBeInTheDocument()
    expect(screen.getByText('Paid')).toBeInTheDocument()
  })

  // D3's rule: no PR ships a button that does nothing, and invoice documents
  // have no source in this application.
  it('offers no download action', () => {
    render(<InvoicesTable invoices={INVOICES} periodEnd="2026-09-29T00:00:00.000Z" />)
    expect(screen.queryByRole('button', { name: /download/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /download/i })).not.toBeInTheDocument()
  })

  it('explains an empty list with the date the first invoice is due', () => {
    render(<InvoicesTable invoices={[]} periodEnd="2026-09-29T00:00:00.000Z" />)

    expect(screen.getByText('No invoices yet')).toBeInTheDocument()
    expect(screen.getByText(/Sep 29, 2026/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
