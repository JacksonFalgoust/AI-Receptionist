import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import type { Integration } from '@/types'

import { IntegrationCard } from './IntegrationCard'

function buildIntegration(overrides: Partial<Integration> = {}): Integration {
  return {
    id: 'int_test',
    organizationId: 'org_test',
    name: 'Horizon CRM',
    category: 'crm',
    status: 'connected',
    features: [],
    ...overrides,
  }
}

describe('IntegrationCard', () => {
  it('shows the name, category, and status', () => {
    render(<IntegrationCard integration={buildIntegration()} />)
    expect(screen.getByRole('heading', { name: 'Horizon CRM' })).toBeInTheDocument()
    expect(screen.getByText('CRM')).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('shows last activity as a relative time when present', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    render(<IntegrationCard integration={buildIntegration({ lastActivityAt: fiveMinutesAgo })} />)
    expect(screen.getByText(/5 minutes ago/)).toBeInTheDocument()
  })

  it('falls back to "No activity yet" when there is no last activity', () => {
    render(<IntegrationCard integration={buildIntegration({ lastActivityAt: undefined })} />)
    expect(screen.getByText(/No activity yet/)).toBeInTheDocument()
  })

  it('shows the connected account when present', () => {
    render(
      <IntegrationCard
        integration={buildIntegration({ connectedAccount: 'ops@horizonpartners.example.com' })}
      />,
    )
    expect(screen.getByText(/ops@horizonpartners.example.com/)).toBeInTheDocument()
  })

  it('does not show a connected-account line when there is none', () => {
    render(<IntegrationCard integration={buildIntegration({ connectedAccount: undefined })} />)
    expect(screen.queryByText(/Account:/)).not.toBeInTheDocument()
  })

  it('lists the features using the connection', () => {
    render(
      <IntegrationCard
        integration={buildIntegration({ features: ['Customer Lookup', 'Human Escalation'] })}
      />,
    )
    expect(screen.getByText(/Customer Lookup, Human Escalation/)).toBeInTheDocument()
  })

  it('says when no feature uses the connection yet', () => {
    render(<IntegrationCard integration={buildIntegration({ features: [] })} />)
    expect(screen.getByText(/Not used by any feature yet/)).toBeInTheDocument()
  })
})
