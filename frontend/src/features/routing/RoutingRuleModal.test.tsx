import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { RoutingRule } from '@/types'

import { RoutingRuleModal } from './RoutingRuleModal'

function keywordRule(): RoutingRule {
  return store.routingRules.find((rule) => rule.condition === 'keyword_match')!
}

describe('RoutingRuleModal', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('creates a rule from a blank form', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const before = store.routingRules.length
    renderWithProviders(<RoutingRuleModal isOpen onClose={onClose} defaultPriority={9} />)

    await user.type(screen.getByLabelText('Rule name'), 'Weekend overflow')
    await user.selectOptions(screen.getByLabelText('When this happens'), 'complaint')
    await user.selectOptions(screen.getByLabelText('Send to'), 'team')
    await user.type(screen.getByLabelText('Team name'), 'Client care')
    await user.click(screen.getByRole('button', { name: 'Create rule' }))

    await vi.waitFor(() => expect(store.routingRules).toHaveLength(before + 1))
    expect(store.routingRules.at(-1)).toMatchObject({
      name: 'Weekend overflow',
      condition: 'complaint',
      destination: { type: 'team', value: 'Client care' },
      priority: 9,
    })
    expect(onClose).toHaveBeenCalled()
  })

  it('loads an existing rule into the form', () => {
    const rule = keywordRule()
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} rule={rule} />)

    expect(screen.getByLabelText('Rule name')).toHaveValue(rule.name)
    expect(screen.getByLabelText('Keywords')).toHaveValue(rule.conditionDetail)
  })

  it('asks for a detail only on the conditions that need one', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} />)

    await user.selectOptions(screen.getByLabelText('When this happens'), 'keyword_match')
    expect(screen.getByLabelText('Keywords')).toBeInTheDocument()

    await user.selectOptions(
      screen.getByLabelText('When this happens'),
      'transaction_over_threshold',
    )
    expect(screen.getByLabelText('Amount threshold')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('When this happens'), 'complaint')
    expect(screen.queryByLabelText('Keywords')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Amount threshold')).not.toBeInTheDocument()
  })

  it('labels the destination value for the type chosen', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} />)

    await user.selectOptions(screen.getByLabelText('Send to'), 'phone_number')
    expect(screen.getByLabelText('Phone number')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Send to'), 'queue')
    expect(screen.getByLabelText('Queue name')).toBeInTheDocument()
  })

  it('refuses a rule with no name and no destination', async () => {
    const user = userEvent.setup()
    const before = store.routingRules.length
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: 'Create rule' }))

    expect(await screen.findByText('Enter a rule name')).toBeInTheDocument()
    expect(screen.getByText('Enter where escalations should go')).toBeInTheDocument()
    expect(store.routingRules).toHaveLength(before)
  })

  it('refuses a keyword rule with no keywords', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} />)

    await user.type(screen.getByLabelText('Rule name'), 'Keyword rule')
    await user.selectOptions(screen.getByLabelText('When this happens'), 'keyword_match')
    await user.type(screen.getByLabelText('Employee name'), 'Sam Rivera')
    await user.click(screen.getByRole('button', { name: 'Create rule' }))

    expect(await screen.findByText(/Enter the keywords this rule matches/)).toBeInTheDocument()
  })

  it('saves an edit through the service', async () => {
    const user = userEvent.setup()
    const rule = keywordRule()
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} rule={rule} />)

    await user.clear(screen.getByLabelText('Rule name'))
    await user.type(screen.getByLabelText('Rule name'), 'Renamed rule')
    await user.click(screen.getByRole('button', { name: 'Save rule' }))

    await vi.waitFor(() =>
      expect(store.routingRules.find((item) => item.id === rule.id)?.name).toBe('Renamed rule'),
    )
  })

  it('offers no delete while creating', () => {
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Delete rule' })).not.toBeInTheDocument()
  })

  it('confirms before deleting', async () => {
    const user = userEvent.setup()
    const rule = keywordRule()
    renderWithProviders(<RoutingRuleModal isOpen onClose={vi.fn()} rule={rule} />)

    await user.click(screen.getByRole('button', { name: 'Delete rule' }))
    await user.click(await screen.findByRole('button', { name: 'Delete' }))

    await vi.waitFor(() =>
      expect(store.routingRules.some((item) => item.id === rule.id)).toBe(false),
    )
  })
})
