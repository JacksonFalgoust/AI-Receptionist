import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'

import { cn } from '@/lib/cn'

// TanStack v9's `RowData` constraint (`Record<string, any> | Array<any>`)
// is narrower than this component's fully-generic `T`. Rather than leak that
// constraint into the public `TableColumn<T>`/`TableProps<T>` interfaces (T
// stays unconstrained there, per the brief), row data is bridged through this
// opaque, RowData-satisfying shape internally and cast back to `T` at the two
// boundaries where real row values cross into/out of TanStack (`cell`'s
// `ctx.row.original` and `getRowId`'s `row` argument).
type OpaqueRow = Record<string, unknown>

export interface TableColumn<T> {
  id: string
  header: string
  render: (row: T) => ReactNode
  sortValue?: (row: T) => string | number
}

export interface TableProps<T> {
  columns: TableColumn<T>[]
  rows: T[]
  getRowId: (row: T) => string
  /**
   * Set false when the table sits inside something that already draws a border
   * — a `Panel`, say — so the two don't stack into a box within a box.
   * Horizontal scrolling is kept either way; it is what makes a wide table
   * usable on a phone, not decoration.
   */
  frame?: boolean
}

type SortDirection = 'asc' | 'desc'

// Sorting is handled entirely by this component (see below) rather than
// TanStack's row-sorting feature, so the shared feature set stays empty.
const features = tableFeatures({})

export function Table<T>({ columns, rows, getRowId, frame = true }: TableProps<T>) {
  const [sort, setSort] = useState<{ columnId: string; direction: SortDirection } | null>(null)

  const sortedRows = useMemo(() => {
    if (!sort) return rows
    const column = columns.find((candidate) => candidate.id === sort.columnId)
    if (!column?.sortValue) return rows
    const withKeys = rows.map((row) => ({ row, key: column.sortValue!(row) }))
    withKeys.sort((a, b) => {
      if (a.key === b.key) return 0
      const comparison = a.key < b.key ? -1 : 1
      return sort.direction === 'asc' ? comparison : -comparison
    })
    return withKeys.map((entry) => entry.row)
  }, [rows, sort, columns])

  const helper = useMemo(() => createColumnHelper<typeof features, OpaqueRow>(), [])

  const tanstackColumns = useMemo(
    () =>
      columns.map((column) =>
        helper.display({
          id: column.id,
          header: column.header,
          cell: (ctx) => column.render(ctx.row.original as unknown as T),
        }),
      ),
    [columns, helper],
  )

  const table = useTable({
    features,
    columns: tanstackColumns,
    data: sortedRows as unknown as OpaqueRow[],
    getRowId: (row) => getRowId(row as unknown as T),
  })

  const toggleSort = (columnId: string) => {
    setSort((current) => {
      if (current?.columnId !== columnId) return { columnId, direction: 'asc' }
      if (current.direction === 'asc') return { columnId, direction: 'desc' }
      return null
    })
  }

  return (
    <div className={cn('table-wrap overflow-x-auto', frame && 'rounded-lg border border-border')}>
      <table className="w-full min-w-max border-collapse text-sm">
        <thead className="sticky top-0 bg-surface">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const column = columns.find((candidate) => candidate.id === header.column.id)
                const isSortable = Boolean(column?.sortValue)
                const isSorted = sort?.columnId === header.column.id ? sort.direction : null

                return (
                  <th
                    key={header.id}
                    scope="col"
                    className="border-b border-border px-3 py-2 text-left font-semibold text-ink-secondary"
                  >
                    {isSortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(header.column.id)}
                        className="inline-flex items-center gap-1"
                        aria-label={`Sort by ${column?.header}${
                          isSorted ? `, currently sorted ${isSorted === 'asc' ? 'ascending' : 'descending'}` : ''
                        }`}
                      >
                        <table.FlexRender header={header} />
                        {isSorted === 'asc' ? (
                          <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                        ) : isSorted === 'desc' ? (
                          <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                        ) : (
                          <ArrowUpDown className="h-3.5 w-3.5 text-ink-muted" aria-hidden />
                        )}
                      </button>
                    ) : (
                      <table.FlexRender header={header} />
                    )}
                  </th>
                )
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-b border-border last:border-0">
              {row.getAllCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  <table.FlexRender cell={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
