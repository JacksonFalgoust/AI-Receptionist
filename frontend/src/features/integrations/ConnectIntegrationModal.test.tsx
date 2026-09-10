import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { AppError } from '@/services/errors'
import { renderWithProviders } from '@/test/renderWithProviders'
import type { Integration } from '@/types'

import { ConnectIntegrationModal } from './ConnectIntegrationModal'

const inventoryIntegration: Integration = {
  id: 'int_test',
  organizationId: 'org_test',
  name: 'StockSync',
  category: 'inventory',
  status: 'connection_error',
  connectedAccount: 'ops@horizonpartners.example.com',
  features: ['Inventory Lookup'],
}

function renderModal(overrides: Partial<Parameters<typeof ConnectIntegrationModal>[0]> = {}) {
  const onSubmit = vi.fn()
  const onClose = vi.fn()
  renderWithProviders(
    <ConnectIntegrationModal
      integration={inventoryIntegration}
      isOpen
      onClose={onClose}
      onSubmit={onSubmit}
      isPending={false}
      error={null}
      {...overrides}
    />,
  )
  return { onSubmit, onClose }
}

describe('ConnectIntegrationModal', () => {
  it('renders the fields the integration category asks for', () => {
    renderModal()
    expect(screen.getByLabelText('Account name')).toBeInTheDocument()
    expect(screen.getByLabelText('API key')).toBeInTheDocument()
    expect(screen.getByLabelText('Warehouse ID')).toBeInTheDocument()
  })

  it('titles itself with the action the status calls for', () => {
    renderModal()
    expect(
      screen.getByRole('heading', { name: /Repair connection — StockSync/ }),
    ).toBeInTheDocument()
  })

  it('prefills the account name but never the secret', () => {
    renderModal()
    expect(screen.getByLabelText('Account name')).toHaveValue('ops@horizonpartners.example.com')
    expect(screen.getByLabelText('API key')).toHaveValue('')
  })

  it('masks every secret field', () => {
    renderModal()
    expect(screen.getByLabelText('API key')).toHaveAttribute('type', 'password')
    expect(screen.getByLabelText('Warehouse ID')).toHaveAttribute('type', 'text')
  })

  it('says that a credential cannot be read back', () => {
    renderModal()
    expect(screen.getByText(/never shown again/i)).toBeInTheDocument()
  })

  it('blocks submission when a required field is empty', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderModal()

    await user.click(screen.getByRole('button', { name: 'Repair connection' }))

    expect(await screen.findByText('API key is required.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits the account label and the entered credentials', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderModal()

    await user.type(screen.getByLabelText('API key'), 'sk-test-123')
    await user.type(screen.getByLabelText('Warehouse ID'), 'wh-1')
    await user.click(screen.getByRole('button', { name: 'Repair connection' }))

    expect(onSubmit).toHaveBeenCalledWith({
      accountLabel: 'ops@horizonpartners.example.com',
      credentials: { apiKey: 'sk-test-123', warehouseId: 'wh-1' },
    })
  })

  it('omits an optional field left blank rather than sending an empty string', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderModal()

    await user.type(screen.getByLabelText('API key'), 'sk-test-123')
    await user.click(screen.getByRole('button', { name: 'Repair connection' }))

    expect(onSubmit).toHaveBeenCalledWith({
      accountLabel: 'ops@horizonpartners.example.com',
      credentials: { apiKey: 'sk-test-123' },
    })
  })

  it('shows a failure inline and keeps what was typed', async () => {
    const user = userEvent.setup()
    renderModal({
      error: new AppError({
        kind: 'server',
        title: 'Could not reach StockSync',
        description: 'The address was refused. Check the API key and try again.',
      }),
    })

    await user.type(screen.getByLabelText('API key'), 'sk-test-123')

    expect(screen.getByText('Could not reach StockSync')).toBeInTheDocument()
    expect(screen.getByLabelText('API key')).toHaveValue('sk-test-123')
  })

  it('cannot be dismissed while a connection attempt is in flight', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal({ isPending: true })

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).not.toHaveBeenCalled()
  })
})
