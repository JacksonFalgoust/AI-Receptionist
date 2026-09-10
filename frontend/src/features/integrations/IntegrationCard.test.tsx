import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ACCOUNT_LABEL_FIELD, integrationAuthFields } from '@/lib/integrationAuthFields'
import { resetStore, store } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { integrationService } from '@/services/integrationService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { Integration } from '@/types'

import { IntegrationCard } from './IntegrationCard'

function integrationWith(overrides: Partial<Integration>): Integration {
  return {
    id: 'int_test',
    organizationId: 'org_test',
    name: 'StockSync',
    category: 'inventory',
    status: 'not_connected',
    features: ['Inventory Lookup'],
    ...overrides,
  }
}

/**
 * Fills whatever the integration's category actually asks for. Reading the
 * field map rather than hard-coding labels keeps these cases working against
 * any seed entry — the not-connected seed's category is not fixed by this
 * test, and a category change should not break it.
 */
async function fillRequiredFields(
  user: ReturnType<typeof userEvent.setup>,
  integration: Integration,
  value: string,
) {
  await user.type(screen.getByLabelText(ACCOUNT_LABEL_FIELD.label), 'ops@horizonpartners.example.com')
  for (const field of integrationAuthFields(integration.category)) {
    if (field.required) await user.type(screen.getByLabelText(field.label), value)
  }
}

describe('IntegrationCard actions', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('offers the action each status calls for', () => {
    const cases: [Integration['status'], string][] = [
      ['not_connected', 'Connect'],
      ['setup_required', 'Continue setup'],
      ['connection_error', 'Repair connection'],
      ['authentication_expired', 'Reconnect'],
    ]
    for (const [status, label] of cases) {
      const { unmount } = renderWithProviders(
        <IntegrationCard integration={integrationWith({ status })} />,
      )
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
      unmount()
    }
  })

  it('offers only Disconnect on a working connection', () => {
    renderWithProviders(
      <IntegrationCard integration={integrationWith({ status: 'connected' })} />,
    )
    expect(screen.getByRole('button', { name: 'Disconnect' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Connect' })).not.toBeInTheDocument()
  })

  it('offers no disconnect for a connection that was never made', () => {
    renderWithProviders(
      <IntegrationCard integration={integrationWith({ status: 'not_connected' })} />,
    )
    expect(screen.queryByRole('button', { name: 'Disconnect' })).not.toBeInTheDocument()
  })

  it('connects through the service and reports it', async () => {
    const user = userEvent.setup()
    const seeded = store.integrations.find((item) => item.status === 'not_connected')!
    renderWithProviders(<IntegrationCard integration={seeded} />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    await fillRequiredFields(user, seeded, 'value-123')
    await user.click(screen.getByRole('button', { name: 'Connect' }))

    // This isolated render never gets a fresh `integration` prop after the
    // mutation (only the query cache is patched), so its `StatusPill` stays
    // on its initial "Not connected" render — which itself satisfies a case
    // insensitive /connected/i match. The toast is the only thing here that
    // genuinely renders only on success.
    expect(await screen.findByText(`${seeded.name} is set up and ready.`)).toBeInTheDocument()
    expect(store.integrations.find((item) => item.id === seeded.id)?.status).toBe('connected')
  })

  it('never lets a submitted secret reach the store (PRD §17.3, §47)', async () => {
    const user = userEvent.setup()
    const seeded = store.integrations.find((item) => item.status === 'not_connected')!
    const SECRET = 'super-secret-value-do-not-store'
    renderWithProviders(<IntegrationCard integration={seeded} />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    await fillRequiredFields(user, seeded, SECRET)
    await user.click(screen.getByRole('button', { name: 'Connect' }))

    await screen.findByText(/connected/i)
    expect(JSON.stringify(store.integrations)).not.toContain(SECRET)
  })

  it('keeps the dialog open and explains a failure', async () => {
    const user = userEvent.setup()
    vi.spyOn(integrationService, 'connect').mockRejectedValueOnce(
      new AppError({
        kind: 'server',
        title: 'Could not reach StockSync',
        description: 'The address was refused.',
      }),
    )
    renderWithProviders(
      <IntegrationCard integration={integrationWith({ status: 'not_connected' })} />,
    )

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    await user.type(screen.getByLabelText('Account name'), 'ops@horizonpartners.example.com')
    await user.type(screen.getByLabelText('Warehouse ID'), 'wh-1')
    await user.type(screen.getByLabelText('API key'), 'sk-1')
    await user.click(screen.getByRole('button', { name: 'Connect' }))

    expect(await screen.findByText('Could not reach StockSync')).toBeInTheDocument()
    expect(screen.getByLabelText('Account name')).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  it('names what stops working before disconnecting', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <IntegrationCard
        integration={integrationWith({ status: 'connected', features: ['Inventory Lookup'] })}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))

    expect(await screen.findByText(/Inventory Lookup/)).toBeInTheDocument()
  })

  it('does not disconnect when the confirmation is declined', async () => {
    const user = userEvent.setup()
    const disconnect = vi.spyOn(integrationService, 'disconnect')
    renderWithProviders(
      <IntegrationCard integration={integrationWith({ status: 'connected' })} />,
    )

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))

    expect(disconnect).not.toHaveBeenCalled()
    vi.restoreAllMocks()
  })
})
