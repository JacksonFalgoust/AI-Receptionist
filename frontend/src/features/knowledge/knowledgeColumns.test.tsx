import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { Table } from '@/components/ui/Table'
import type { KnowledgeItem } from '@/types'

import { KNOWLEDGE_COLUMNS } from './knowledgeColumns'

const base: KnowledgeItem = {
  id: 'kn_0007',
  organizationId: 'org_horizon',
  title: 'Refund policy',
  type: 'policy',
  status: 'needs_review',
  source: 'Manual entry',
  category: 'Policies',
  content: 'Refund requests are reviewed within five business days.',
  tags: ['policy', 'refunds'],
  updatedAt: '2026-09-03T14:12:00.000Z',
}

function renderRows(rows: KnowledgeItem[]) {
  render(
    <MemoryRouter>
      <Table columns={KNOWLEDGE_COLUMNS} rows={rows} getRowId={(row) => row.id} frame={false} />
    </MemoryRouter>,
  )
}

describe('knowledge columns', () => {
  it('shows the six columns PRD §16.2 asks for, in order', () => {
    renderRows([base])
    expect(screen.getAllByRole('columnheader').map((header) => header.textContent?.trim())).toEqual([
      'Name',
      'Type',
      'Status',
      'Source',
      'Updated',
      'Actions',
    ])
  })

  it('names the type in business language', () => {
    renderRows([{ ...base, type: 'document' }])
    expect(screen.getByText('Uploaded document')).toBeInTheDocument()
  })

  it('states the status in words, not colour alone', () => {
    renderRows([base])
    expect(screen.getByText('Needs review')).toBeInTheDocument()
  })

  it('links the name to that item in the editor', () => {
    renderRows([base])
    expect(screen.getByRole('link', { name: 'Refund policy' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/kn_0007',
    )
  })

  it('offers Edit in the Actions column', () => {
    renderRows([base])
    expect(screen.getByRole('link', { name: 'Edit Refund policy' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/kn_0007',
    )
  })

  it('offers View, not Edit, while an item is still being processed', () => {
    // Nothing is editable until the upload has been read; offering Edit would
    // promise a form that cannot yet be filled in.
    renderRows([{ ...base, title: 'Client handbook', type: 'document', status: 'processing' }])
    expect(screen.getByRole('link', { name: 'View Client handbook' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Edit/ })).not.toBeInTheDocument()
  })

  it('shows where an item came from', () => {
    renderRows([{ ...base, source: 'client-handbook-2026.pdf' }])
    expect(screen.getByText('client-handbook-2026.pdf')).toBeInTheDocument()
  })

  it('formats the updated timestamp for scanning', () => {
    renderRows([base])
    const row = screen.getByRole('link', { name: 'Refund policy' }).closest('tr')!
    expect(within(row).getByText(/Sep 3, 2026/)).toBeInTheDocument()
  })

  // Same reasoning as the conversation columns: Table sorts only the rows on
  // the current page, so a sort control would misrepresent itself as sorting
  // the whole library. Real sorting is server-side and not part of US-5.1.
  it('offers no column sorting', () => {
    renderRows([base])
    expect(screen.queryByRole('button', { name: /sort by/i })).not.toBeInTheDocument()
  })
})
