import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { RoutingRule } from '@/types'

import { RoutingRulesTable } from './RoutingRulesTable'

function rules(): RoutingRule[] {
  return [...store.routingRules].sort((a, b) => a.priority - b.priority)
}

describe('RoutingRulesTable', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('renders the six PRD §18.4 columns', () => {
    renderWithProviders(<RoutingRulesTable rules={rules()} />)
    for (const header of ['Rule', 'Condition', 'Destination', 'Schedule', 'Priority', 'Status']) {
      expect(screen.getByRole('columnheader', { name: new RegExp(header) })).toBeInTheDocument()
    }
  })

  it('names conditions, destinations, and schedules in business language', () => {
    renderWithProviders(<RoutingRulesTable rules={rules()} />)
    expect(screen.getByText('Customer asks for a person')).toBeInTheDocument()
    expect(screen.getAllByText('Open hours').length).toBeGreaterThan(0)
    expect(screen.queryByText('customer_requests_person')).not.toBeInTheDocument()
  })

  it('shows the detail a condition is meaningless without', () => {
    renderWithProviders(<RoutingRulesTable rules={rules()} />)
    expect(screen.getByText('Over $2,000')).toBeInTheDocument()
    expect(screen.getByText('urgent, deadline, board meeting')).toBeInTheDocument()
  })

  it('qualifies a destination with its type', () => {
    renderWithProviders(<RoutingRulesTable rules={rules()} />)
    expect(screen.getByText('Client care queue')).toBeInTheDocument()
    expect(screen.getAllByText('Queue').length).toBeGreaterThan(0)
  })

  it('states each rule status in words, never colour alone', () => {
    renderWithProviders(<RoutingRulesTable rules={rules()} />)
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Inactive').length).toBeGreaterThan(0)
  })

  it('turns a rule off through the service', async () => {
    const user = userEvent.setup()
    const target = rules()[0]
    renderWithProviders(<RoutingRulesTable rules={rules()} />)

    const row = screen.getByRole('row', { name: new RegExp(target.name) })
    await user.click(within(row).getByRole('switch'))

    expect(await screen.findByText(/no longer/i)).toBeInTheDocument()
    expect(store.routingRules.find((rule) => rule.id === target.id)?.enabled).toBe(false)
  })
})
