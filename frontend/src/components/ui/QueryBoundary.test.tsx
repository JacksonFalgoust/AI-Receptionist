import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { AppError } from '@/services/errors'

import { QueryBoundary } from './QueryBoundary'
import type { QueryBoundaryProps, QueryBoundaryResult } from './QueryBoundary'

interface Row {
  items: string[]
}

function result(overrides: Partial<QueryBoundaryResult<Row>>): QueryBoundaryResult<Row> {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    ...overrides,
  }
}

function renderBoundary(
  query: QueryBoundaryResult<Row>,
  extra: Partial<QueryBoundaryProps<Row>> = {},
) {
  return render(
    <MemoryRouter>
      <QueryBoundary
        query={query}
        isEmpty={(data) => data.items.length === 0}
        empty={{ title: 'No conversations yet' }}
        {...extra}
      >
        {(data) => <ul>{data.items.map((item) => <li key={item}>{item}</li>)}</ul>}
      </QueryBoundary>
    </MemoryRouter>,
  )
}

describe('QueryBoundary', () => {
  it('renders a skeleton while pending', () => {
    renderBoundary(result({ isPending: true }))
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })

  it('renders the requested skeleton variant', () => {
    const { container } = renderBoundary(result({ isPending: true }), {
      skeleton: 'table',
      skeletonRows: 5,
    })
    expect(container.querySelectorAll('[data-skeleton-row]')).toHaveLength(5)
  })

  it('renders a custom loading node instead of the default skeleton', () => {
    renderBoundary(result({ isPending: true }), {
      loading: <p>Loading key metrics</p>,
    })
    expect(screen.getByText('Loading key metrics')).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading' })).not.toBeInTheDocument()
  })

  it('renders an error state with a retry bound to refetch', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    renderBoundary(
      result({
        isError: true,
        error: new AppError({
          kind: 'server',
          title: 'Something went wrong on our side',
          description: 'Try again in a moment.',
          actions: [{ label: 'Retry', retry: true }],
        }),
        refetch,
      }),
    )

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(refetch).toHaveBeenCalledOnce()
  })

  it('renders nothing for an unauthorized error, because a redirect is in flight', () => {
    const { container } = renderBoundary(
      result({
        isError: true,
        error: new AppError({
          kind: 'unauthorized',
          title: 'Your session has expired',
          description: 'Sign in again to continue.',
        }),
      }),
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the empty state when isEmpty returns true', () => {
    renderBoundary(result({ data: { items: [] } }))
    expect(screen.getByText('No conversations yet')).toBeInTheDocument()
  })

  it('renders children with narrowed data on success', () => {
    renderBoundary(result({ data: { items: ['Alex Morgan', 'Dana Wu'] } }))
    expect(screen.getByText('Alex Morgan')).toBeInTheDocument()
    expect(screen.getByText('Dana Wu')).toBeInTheDocument()
  })

  it('renders children when no isEmpty predicate is supplied', () => {
    render(
      <MemoryRouter>
        <QueryBoundary query={result({ data: { items: [] } })}>
          {() => <p>Always rendered</p>}
        </QueryBoundary>
      </MemoryRouter>,
    )
    expect(screen.getByText('Always rendered')).toBeInTheDocument()
  })
})
