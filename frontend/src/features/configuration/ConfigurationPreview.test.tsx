import { beforeEach, describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { renderWithProviders, seedSession } from '@/test/renderWithProviders'
import type { ConciergeIdentity } from '@/types'

import { ConfigurationPreview } from './ConfigurationPreview'

const identity: ConciergeIdentity = {
  name: 'Horizon Concierge',
  greeting: 'Thanks for contacting Horizon Partners. How can I help today?',
  closing: 'Thanks for your time. We look forward to speaking again.',
  voice: 'Avery — Warm',
  tone: 'friendly',
  primaryLanguage: 'en-US',
  supportedLanguages: ['en-US'],
}

function renderPreview() {
  renderWithProviders(<ConfigurationPreview identity={identity} />)
}

describe('ConfigurationPreview', () => {
  beforeEach(() => {
    seedSession()
  })

  it('shows the saved greeting', () => {
    renderPreview()
    expect(
      screen.getByText('Thanks for contacting Horizon Partners. How can I help today?'),
    ).toBeInTheDocument()
  })

  it('shows the saved closing message', () => {
    renderPreview()
    expect(
      screen.getByText('Thanks for your time. We look forward to speaking again.'),
    ).toBeInTheDocument()
  })

  it('opens the test drawer instead of navigating', async () => {
    const user = userEvent.setup()
    renderPreview()

    await user.click(screen.getByRole('button', { name: 'Test Concierge' }))
    expect(await screen.findByRole('dialog', { name: 'Test Concierge' })).toBeInTheDocument()
  })
})
