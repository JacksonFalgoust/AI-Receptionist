import { beforeEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore, store } from '@/mocks/store'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { FeaturesPage } from './FeaturesPage'

describe('FeaturesPage', () => {
  beforeEach(() => {
    resetStore()
    seedSession()
  })

  it('is a built screen, not a placeholder', async () => {
    renderWithProviders(<FeaturesPage />)
    expect(screen.getByRole('heading', { name: 'Features' })).toBeInTheDocument()
    expect(screen.queryByText(/has not been built yet/i)).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Answer Calls' })).toBeInTheDocument()
  })

  it('loads behind a loading state', async () => {
    renderWithProviders(<FeaturesPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Answer Calls' })).toBeInTheDocument()
  })

  it('renders one card per seeded feature', async () => {
    renderWithProviders(<FeaturesPage />)
    await screen.findByRole('heading', { name: 'Answer Calls' })
    expect(screen.getAllByRole('switch')).toHaveLength(store.features.length)
  })

  it('reflects a toggle across the whole page once it succeeds', async () => {
    const user = userEvent.setup()
    renderWithProviders(<FeaturesPage />)
    await screen.findByRole('heading', { name: 'Answer Calls' })

    const smsCard = screen.getByRole('group', { name: 'SMS' })
    await user.click(within(smsCard).getByRole('switch', { name: 'Enable SMS' }))

    expect(await within(smsCard).findByText('Disabled')).toBeInTheDocument()
    expect(within(smsCard).getByRole('switch', { name: 'Enable SMS' })).not.toBeChecked()
  })
})
