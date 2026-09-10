import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'

import { resetStore, store } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { routingService } from '@/services/routingService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { RoutingPage } from './RoutingPage'

describe('RoutingPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<RoutingPage />)
    expect(screen.getByRole('heading', { name: 'Escalation & Routing' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByText('Client asks for a person')).toBeInTheDocument()
  })

  it('loads behind a loading state', async () => {
    renderWithProviders(<RoutingPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByText('Client asks for a person')).toBeInTheDocument()
  })

  it('counts the rules that are actually routing', async () => {
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')
    const active = store.routingRules.filter((rule) => rule.enabled).length
    expect(screen.getByText('Active rules').closest('div')).toHaveTextContent(String(active))
  })

  it('reports escalations today', async () => {
    renderWithProviders(<RoutingPage />)
    expect(await screen.findByText('Escalations today')).toBeInTheDocument()
  })

  it('renders one row per seeded rule', async () => {
    renderWithProviders(<RoutingPage />)
    await screen.findByText('Client asks for a person')
    // One row per rule, plus the header row.
    expect(screen.getAllByRole('row')).toHaveLength(store.routingRules.length + 1)
  })

  it('invites a first rule when there are none', async () => {
    store.routingRules = []
    renderWithProviders(<RoutingPage />)
    expect(await screen.findByText('Create your first routing rule')).toBeInTheDocument()
  })

  it('explains a failure to load', async () => {
    vi.spyOn(routingService, 'list').mockRejectedValueOnce(
      new AppError({
        kind: 'server',
        title: 'Could not load routing rules',
        description: 'Try again in a moment.',
      }),
    )
    renderWithProviders(<RoutingPage />)
    expect(await screen.findByText('Could not load routing rules')).toBeInTheDocument()
    vi.restoreAllMocks()
  })
})
