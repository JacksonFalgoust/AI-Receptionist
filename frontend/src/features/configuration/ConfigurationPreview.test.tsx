import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

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
  render(
    <MemoryRouter>
      <ConfigurationPreview identity={identity} />
    </MemoryRouter>,
  )
}

describe('ConfigurationPreview', () => {
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

  it('links Test Concierge to the /test route', () => {
    renderPreview()
    expect(screen.getByRole('link', { name: 'Test Concierge' })).toHaveAttribute('href', '/test')
  })
})
