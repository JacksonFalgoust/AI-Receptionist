import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Table } from './Table'
import type { TableColumn } from './Table'

interface Row {
  id: string
  name: string
  age: number
}

const rows: Row[] = [
  { id: '1', name: 'Bea', age: 41 },
  { id: '2', name: 'Ada', age: 36 },
]

const columns: TableColumn<Row>[] = [
  { id: 'name', header: 'Name', render: (row) => row.name, sortValue: (row) => row.name },
  { id: 'age', header: 'Age', render: (row) => String(row.age), sortValue: (row) => row.age },
]

describe('Table', () => {
  it('renders one header per column and one row per item', () => {
    render(<Table columns={columns} rows={rows} getRowId={(row) => row.id} />)
    expect(screen.getByRole('columnheader', { name: /name/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /age/i })).toBeInTheDocument()
    expect(screen.getByText('Bea')).toBeInTheDocument()
    expect(screen.getByText('Ada')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(3)
  })

  it('sorts ascending then descending then back to unsorted on repeated header clicks', async () => {
    const user = userEvent.setup()
    render(<Table columns={columns} rows={rows} getRowId={(row) => row.id} />)
    const sortButton = screen.getByRole('button', { name: /sort by name/i })

    await user.click(sortButton)
    let cells = screen.getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('Ada')

    await user.click(sortButton)
    cells = screen.getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('Bea')

    await user.click(sortButton)
    cells = screen.getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('Bea')
  })

  it('renders no sort control for a column without sortValue', () => {
    const readOnlyColumns: TableColumn<Row>[] = [{ id: 'name', header: 'Name', render: (row) => row.name }]
    render(<Table columns={readOnlyColumns} rows={rows} getRowId={(row) => row.id} />)
    expect(screen.queryByRole('button', { name: /sort/i })).not.toBeInTheDocument()
  })

  it('draws its own frame by default', () => {
    const { container } = render(<Table columns={columns} rows={rows} getRowId={(row) => row.id} />)
    const wrap = container.querySelector('.table-wrap')
    expect(wrap).toHaveClass('border')
    expect(wrap).toHaveClass('overflow-x-auto')
  })

  it('drops its frame when a container already supplies one, but still scrolls', () => {
    const { container } = render(
      <Table columns={columns} rows={rows} getRowId={(row) => row.id} frame={false} />,
    )
    const wrap = container.querySelector('.table-wrap')
    expect(wrap).not.toHaveClass('border')
    expect(wrap).toHaveClass('overflow-x-auto')
  })
})
