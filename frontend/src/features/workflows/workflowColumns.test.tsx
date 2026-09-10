import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { Table } from '@/components/ui/Table'
import type { Workflow } from '@/types'

import { WORKFLOW_COLUMNS } from './workflowColumns'

const base: Workflow = {
  id: 'wf_0001',
  organizationId: 'org_horizon',
  name: 'Book an appointment',
  description: 'Collects what the client needs, checks availability, and confirms the booking.',
  status: 'active',
  version: 7,
  executionCount: 1284,
  steps: [],
  lastUpdatedAt: '2026-09-02T14:12:00.000Z',
}

function renderRows(rows: Workflow[]) {
  render(
    <MemoryRouter>
      <Table columns={WORKFLOW_COLUMNS} rows={rows} getRowId={(row) => row.id} frame={false} />
    </MemoryRouter>,
  )
}

describe('workflow columns', () => {
  it('shows the six columns PRD §15.1 asks for, in order', () => {
    renderRows([base])
    expect(screen.getAllByRole('columnheader').map((header) => header.textContent?.trim())).toEqual([
      'Name',
      'Description',
      'Status',
      'Version',
      'Executions',
      'Updated',
    ])
  })

  it('links the name to that workflow', () => {
    renderRows([base])
    expect(screen.getByRole('link', { name: 'Book an appointment' })).toHaveAttribute(
      'href',
      '/concierge/workflows/wf_0001',
    )
  })

  it('shows the description', () => {
    renderRows([base])
    expect(
      screen.getByText('Collects what the client needs, checks availability, and confirms the booking.'),
    ).toBeInTheDocument()
  })

  it('shows an em dash rather than a blank cell when there is no description', () => {
    renderRows([{ ...base, description: undefined }])
    const row = screen.getByRole('link', { name: 'Book an appointment' }).closest('tr')!
    expect(within(row).getByText('—')).toBeInTheDocument()
  })

  it('states the status in words, not colour alone', () => {
    renderRows([base])
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows a draft workflow as Draft', () => {
    renderRows([{ ...base, status: 'draft' }])
    expect(screen.getByText('Draft')).toBeInTheDocument()
  })

  it('labels the version with a v prefix', () => {
    renderRows([base])
    expect(screen.getByText('v7')).toBeInTheDocument()
  })

  it('formats the execution count with thousands separators', () => {
    renderRows([base])
    expect(screen.getByText('1,284')).toBeInTheDocument()
  })

  it('formats the updated timestamp for scanning', () => {
    renderRows([base])
    const row = screen.getByRole('link', { name: 'Book an appointment' }).closest('tr')!
    expect(within(row).getByText(/Sep 2, 2026/)).toBeInTheDocument()
  })

  it('offers no column sorting', () => {
    renderRows([base])
    expect(screen.queryByRole('button', { name: /sort by/i })).not.toBeInTheDocument()
  })
})
