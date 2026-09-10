import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { Feature } from '@/types'

import { FeatureCard } from './FeatureCard'

function findSeeded(id: string): Feature {
  const feature = store.features.find((item) => item.id === id)
  if (!feature) throw new Error(`Fixture drift: ${id} is no longer seeded`)
  return feature
}

function renderCard(feature: Feature) {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<FeatureCard feature={feature} />} />
      <Route path="/integrations" element={<h1>Integrations</h1>} />
    </Routes>,
  )
}

describe('FeatureCard', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('shows name, description, status, and the required integration', () => {
    renderCard(findSeeded('feat_inventory'))
    expect(screen.getByRole('heading', { name: 'Inventory Lookup' })).toBeInTheDocument()
    expect(screen.getByText('Check availability of services and resources.')).toBeInTheDocument()
    expect(screen.getByText('Setup required')).toBeInTheDocument()
    expect(screen.getByText('Requires Inventory')).toBeInTheDocument()
  })

  it('shows the toggle checked for an enabled feature', () => {
    renderCard(findSeeded('feat_sms'))
    expect(screen.getByRole('switch', { name: 'Enable SMS' })).toBeChecked()
  })

  it('shows the toggle unchecked for a disabled feature', () => {
    renderCard(findSeeded('feat_surveys'))
    expect(screen.getByRole('switch', { name: 'Enable Follow-up Surveys' })).not.toBeChecked()
  })

  it('disables a non-high-impact feature without asking to confirm', async () => {
    const user = userEvent.setup()
    renderCard(findSeeded('feat_sms'))

    await user.click(screen.getByRole('switch', { name: 'Enable SMS' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(await screen.findByText('Feature turned off.')).toBeInTheDocument()
    expect(store.features.find((f) => f.id === 'feat_sms')?.status).toBe('disabled')
  })

  it('asks to confirm before disabling a high-impact feature, and honors Cancel', async () => {
    const user = userEvent.setup()
    renderCard(findSeeded('feat_payments'))

    await user.click(screen.getByRole('switch', { name: 'Enable Payments' }))
    const dialogElement = await screen.findByRole('dialog')
    expect(dialogElement).toHaveTextContent(
      'Concierge will no longer be able to use Payments until this is turned back on.',
    )
    await user.click(within(dialogElement).getByRole('button', { name: 'Cancel' }))

    expect(store.features.find((f) => f.id === 'feat_payments')?.status).toBe('enabled')
  })

  it('disables a high-impact feature once confirmed', async () => {
    const user = userEvent.setup()
    renderCard(findSeeded('feat_payments'))

    await user.click(screen.getByRole('switch', { name: 'Enable Payments' }))
    const dialog = within(await screen.findByRole('dialog'))
    await user.click(dialog.getByRole('button', { name: 'Turn off' }))

    expect(await screen.findByText('Feature turned off.')).toBeInTheDocument()
    expect(store.features.find((f) => f.id === 'feat_payments')?.status).toBe('disabled')
  })

  it('enables a feature with nothing blocking it', async () => {
    const user = userEvent.setup()
    renderCard(findSeeded('feat_surveys'))

    await user.click(screen.getByRole('switch', { name: 'Enable Follow-up Surveys' }))

    expect(await screen.findByText('Feature turned on.')).toBeInTheDocument()
    expect(store.features.find((f) => f.id === 'feat_surveys')?.status).toBe('enabled')
  })

  it('shows the next step inline when turning on something that still needs setup', async () => {
    const user = userEvent.setup()
    renderCard(findSeeded('feat_inventory'))

    await user.click(screen.getByRole('switch', { name: 'Enable Inventory Lookup' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/needs setup/i)
    expect(store.features.find((f) => f.id === 'feat_inventory')?.status).toBe('setup_required')
  })

  it('routes to Integrations from the inline next-step action', async () => {
    const user = userEvent.setup()
    renderCard(findSeeded('feat_inventory'))

    await user.click(screen.getByRole('switch', { name: 'Enable Inventory Lookup' }))
    const alert = within(await screen.findByRole('alert'))
    await user.click(alert.getByRole('button', { name: 'View integration' }))

    expect(await screen.findByRole('heading', { name: 'Integrations' })).toBeInTheDocument()
  })

  it('falls back to a toast for an error that is not a setup problem', async () => {
    const user = userEvent.setup()
    // Not a seeded id — the service raises not_found, standing in for any
    // failure this card has no specific next step for.
    renderCard({ ...findSeeded('feat_sms'), id: 'feat_ghost' })

    await user.click(screen.getByRole('switch', { name: 'Enable SMS' }))

    expect(await screen.findByText(/no longer exists/i)).toBeInTheDocument()
  })
})
