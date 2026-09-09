import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { Table } from '@/components/ui/Table'
import type { Conversation } from '@/types'

import { CONVERSATION_COLUMNS } from './conversationColumns'

const base: Conversation = {
  id: 'conv_0002',
  organizationId: 'org_horizon',
  customerName: 'Dana Wu',
  channel: 'voice',
  startedAt: '2026-09-08T18:27:00.000Z',
  durationSeconds: 252,
  intent: 'Refund question',
  outcome: 'escalated',
  escalated: true,
  escalationStatus: 'in_progress',
}

function renderRows(rows: Conversation[]) {
  render(
    <MemoryRouter>
      <Table columns={CONVERSATION_COLUMNS} rows={rows} getRowId={(row) => row.id} frame={false} />
    </MemoryRouter>,
  )
}

describe('conversation columns', () => {
  it('shows the eight columns US-3.1 asks for, in order', () => {
    renderRows([base])
    expect(screen.getAllByRole('columnheader').map((header) => header.textContent?.trim())).toEqual([
      'Date / Time',
      'Customer',
      'Channel',
      'Intent',
      'Outcome',
      'Duration',
      'Escalated',
      'Status',
    ])
  })

  it('prefers the escalation status over the outcome in Status', () => {
    renderRows([base])
    const row = screen.getByText('Dana Wu').closest('tr')!
    expect(row).toHaveTextContent('In progress')
  })

  it('falls back to the outcome when nothing escalated', () => {
    renderRows([{ ...base, outcome: 'completed', escalated: false, escalationStatus: undefined }])
    const row = screen.getByText('Dana Wu').closest('tr')!
    expect(within(row).getAllByText('Completed')).toHaveLength(2)
  })

  it('says whether a conversation escalated in words, not colour', () => {
    renderRows([base])
    expect(screen.getByText('Dana Wu').closest('tr')).toHaveTextContent('Yes')
  })

  it('links the timestamp to the conversation', () => {
    renderRows([base])
    expect(screen.getByRole('link')).toHaveAttribute('href', '/conversations/conv_0002')
  })

  it('names an unidentified caller rather than leaving the cell blank', () => {
    renderRows([{ ...base, customerName: undefined, intent: undefined }])
    expect(screen.getByText('Unknown caller')).toBeInTheDocument()
  })

  it('formats duration for scanning', () => {
    renderRows([base])
    expect(screen.getByText('4m 12s')).toBeInTheDocument()
  })

  // Table only ever sorts the 25 rows on the current page, and any sort
  // resets when a new page is fetched (see Table.tsx / ConversationsPage.tsx)
  // — offering a sort control at this page size would silently misrepresent
  // itself as sorting all 70. Real sorting needs to be server-side, which is
  // not part of US-3.1, so no column here declares `sortValue`.
  it('offers no column sorting', () => {
    renderRows([base])
    expect(screen.queryByRole('button', { name: /sort by/i })).not.toBeInTheDocument()
  })
})
