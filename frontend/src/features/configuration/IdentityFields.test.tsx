import { zodResolver } from '@hookform/resolvers/zod'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm } from 'react-hook-form'
import { MemoryRouter } from 'react-router-dom'

import { AuthProvider } from '@/features/auth/AuthProvider'
import { TestConciergeDrawer } from '@/features/testConcierge/TestConciergeDrawer'
import { TestConciergeDrawerProvider } from '@/features/testConcierge/TestConciergeDrawerContext'
import { seedSession } from '@/test/renderWithProviders'
import type { ConciergeConfiguration } from '@/types'

import {
  configurationFormSchema,
  configurationToFormValues,
} from './configurationFormSchema'
import type { ConfigurationFormValues } from './configurationFormSchema'
import { IdentityFields } from './IdentityFields'

const configuration: ConciergeConfiguration = {
  organizationId: 'org_horizon',
  businessProfile: {
    name: 'Horizon Partners',
    description: '',
    phone: '+1 555 0100',
    website: '',
    timezone: 'America/Chicago',
    address: '1200 Meridian Way, Suite 400',
    locations: '',
    hours: Array.from({ length: 7 }, (_, day) => ({ day, closed: true })),
  },
  identity: {
    name: 'Horizon Concierge',
    greeting: 'Thanks for contacting Horizon Partners.',
    closing: 'Thanks for your time.',
    voice: 'Avery — Warm',
    tone: 'friendly',
    primaryLanguage: 'en-US',
    supportedLanguages: ['en-US', 'es-US'],
  },
  terminology: {
    customer: 'Client',
    reservation: 'Appointment',
    location: 'Office',
    employee: 'Team member',
  },
  hasUnpublishedChanges: false,
}

function Harness({
  onSubmit,
  onPreviewGreeting = () => {},
  configurationOverrides,
}: {
  onSubmit: (values: ConfigurationFormValues) => void
  onPreviewGreeting?: () => void
  configurationOverrides?: Partial<ConciergeConfiguration>
}) {
  const form = useForm<ConfigurationFormValues>({
    defaultValues: configurationToFormValues({ ...configuration, ...configurationOverrides }),
    resolver: zodResolver(configurationFormSchema),
  })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthProvider>
          <TestConciergeDrawerProvider>
            <FormProvider {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)}>
                <IdentityFields onPreviewGreeting={onPreviewGreeting} />
                <button type="submit">Submit</button>
              </form>
            </FormProvider>
            <TestConciergeDrawer />
          </TestConciergeDrawerProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function renderFields(props: Partial<React.ComponentProps<typeof Harness>> = {}) {
  const onSubmit = vi.fn()
  render(<Harness onSubmit={onSubmit} {...props} />)
  return { onSubmit }
}

describe('IdentityFields', () => {
  beforeEach(() => {
    seedSession()
  })

  it('renders every field US-6.1 asks for', () => {
    renderFields()
    expect(screen.getByLabelText('Concierge name')).toBeInTheDocument()
    expect(screen.getByLabelText('Greeting')).toBeInTheDocument()
    expect(screen.getByLabelText('Closing message')).toBeInTheDocument()
    expect(screen.getByLabelText('Voice')).toBeInTheDocument()
    expect(screen.getByLabelText('Tone')).toBeInTheDocument()
    expect(screen.getByLabelText('Primary language')).toBeInTheDocument()
    expect(screen.getByText('Supported languages')).toBeInTheDocument()
  })

  it('pre-fills from the shared form context', () => {
    renderFields()
    expect(screen.getByDisplayValue('Horizon Concierge')).toBeInTheDocument()
    expect(screen.getByLabelText('Tone')).toHaveValue('friendly')
  })

  it('shows a custom tone description only once Custom is selected', async () => {
    const user = userEvent.setup()
    renderFields()

    expect(screen.queryByLabelText('Custom tone description')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Tone'), 'custom')
    expect(screen.getByLabelText('Custom tone description')).toBeInTheDocument()
  })

  it('keeps a voice that is not in the curated list selected instead of blanking it', () => {
    renderFields({
      configurationOverrides: {
        identity: { ...configuration.identity, voice: 'Legacy voice not in the catalog' },
      },
    })
    expect(screen.getByLabelText('Voice')).toHaveValue('Legacy voice not in the catalog')
  })

  it('keeps a primary language that is not in the curated list selected instead of blanking it', () => {
    renderFields({
      configurationOverrides: {
        identity: { ...configuration.identity, primaryLanguage: 'de-DE' },
      },
    })
    expect(screen.getByLabelText('Primary language')).toHaveValue('de-DE')
  })

  it('keeps a supported language that is not in the curated list checked instead of silently dropping it', () => {
    renderFields({
      configurationOverrides: {
        identity: {
          ...configuration.identity,
          primaryLanguage: 'de-DE',
          supportedLanguages: ['en-US', 'de-DE'],
        },
      },
    })
    expect(screen.getByRole('checkbox', { name: 'de-DE' })).toBeChecked()
  })

  it('checks a supported language box for each seeded language', () => {
    renderFields()
    expect(screen.getByRole('checkbox', { name: 'English (US)' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Spanish (US)' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'French (Canada)' })).not.toBeChecked()
  })

  it('toggles a supported language on and off', async () => {
    const user = userEvent.setup()
    renderFields()

    const french = screen.getByRole('checkbox', { name: 'French (Canada)' })
    await user.click(french)
    expect(french).toBeChecked()
    await user.click(french)
    expect(french).not.toBeChecked()
  })

  it('calls onPreviewGreeting when Preview greeting is clicked', async () => {
    const user = userEvent.setup()
    const onPreviewGreeting = vi.fn()
    renderFields({ onPreviewGreeting })

    await user.click(screen.getByRole('button', { name: 'Preview greeting' }))
    expect(onPreviewGreeting).toHaveBeenCalled()
  })

  it('opens the test drawer instead of navigating', async () => {
    const user = userEvent.setup()
    renderFields()

    await user.click(screen.getByRole('button', { name: 'Test Concierge' }))
    expect(await screen.findByRole('dialog', { name: 'Test Concierge' })).toBeInTheDocument()
  })

  it('shows a validation error and does not submit when the name is blank', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFields()

    const name = screen.getByLabelText('Concierge name')
    await user.clear(name)
    await user.click(screen.getByRole('button', { name: 'Submit' }))

    expect(await screen.findByText('Enter a Concierge name')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits under the identity key when the whole form is valid', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFields()

    const name = screen.getByLabelText('Concierge name')
    await user.clear(name)
    await user.type(name, 'Meridian Concierge')
    await user.click(screen.getByRole('button', { name: 'Submit' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          identity: expect.objectContaining({ name: 'Meridian Concierge' }),
        }),
        expect.anything(),
      ),
    )
  })
})
