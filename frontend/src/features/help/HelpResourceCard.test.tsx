import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { HelpResourceCard } from './HelpResourceCard'
import type { HelpResource } from './helpResources'

const GATED_RESOURCE: HelpResource = {
  title: 'Integration guides',
  description: 'Connect CRM, scheduling, payments, and custom tools.',
  action: {
    label: 'View integrations',
    href: '/integrations',
    permission: 'manage:integrations',
  },
}

const UNGATED_RESOURCE: HelpResource = {
  title: 'Contact support',
  description: 'Reach GuideAnts support for account or product help.',
  action: { label: 'Contact support', href: 'mailto:support@guideants.example' },
}

const NO_ACTION_RESOURCE: HelpResource = {
  title: 'Configuration guides',
  description: 'Identity, hours, terminology, and publish workflow.',
}

describe('HelpResourceCard', () => {
  it('renders the title and description', () => {
    renderWithProviders(<HelpResourceCard resource={NO_ACTION_RESOURCE} />)
    expect(screen.getByText('Configuration guides')).toBeInTheDocument()
    expect(
      screen.getByText('Identity, hours, terminology, and publish workflow.'),
    ).toBeInTheDocument()
  })

  it('renders no action when the resource has none', () => {
    renderWithProviders(<HelpResourceCard resource={NO_ACTION_RESOURCE} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('renders a permission-gated link for a role that holds the permission', () => {
    seedSession('administrator@horizonpartners.example.com')
    renderWithProviders(<HelpResourceCard resource={GATED_RESOURCE} />)
    expect(screen.getByRole('link', { name: 'View integrations' })).toHaveAttribute(
      'href',
      '/integrations',
    )
  })

  it('hides a permission-gated link for a role that lacks it', () => {
    seedSession('viewer@horizonpartners.example.com')
    renderWithProviders(<HelpResourceCard resource={GATED_RESOURCE} />)
    expect(screen.queryByRole('link', { name: 'View integrations' })).not.toBeInTheDocument()
  })

  it('renders an ungated mailto action for every role', () => {
    seedSession('viewer@horizonpartners.example.com')
    renderWithProviders(<HelpResourceCard resource={UNGATED_RESOURCE} />)
    expect(screen.getByRole('link', { name: 'Contact support' })).toHaveAttribute(
      'href',
      'mailto:support@guideants.example',
    )
  })
})
