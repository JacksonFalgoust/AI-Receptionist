import { zodResolver } from '@hookform/resolvers/zod'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm } from 'react-hook-form'

import {
  configurationFormSchema,
  configurationToFormValues,
} from './configurationFormSchema'
import type { ConfigurationFormValues } from './configurationFormSchema'
import { BusinessProfileFields } from './BusinessProfileFields'
import type { ConciergeConfiguration } from '@/types'

const configuration: ConciergeConfiguration = {
  organizationId: 'org_horizon',
  businessProfile: {
    name: 'Horizon Partners',
    description: 'A professional services firm.',
    phone: '+1 555 0100',
    website: 'https://horizonpartners.example.com',
    timezone: 'America/Chicago',
    address: '1200 Meridian Way, Suite 400',
    locations: '3 locations',
    hours: [
      { day: 0, closed: true },
      { day: 1, open: '08:30', close: '17:30', closed: false },
      { day: 2, open: '08:30', close: '17:30', closed: false },
      { day: 3, open: '08:30', close: '17:30', closed: false },
      { day: 4, open: '08:30', close: '17:30', closed: false },
      { day: 5, open: '08:30', close: '16:00', closed: false },
      { day: 6, closed: true },
    ],
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
  configurationOverrides,
}: {
  onSubmit: (values: ConfigurationFormValues) => void
  configurationOverrides?: Partial<ConciergeConfiguration>
}) {
  const form = useForm<ConfigurationFormValues>({
    defaultValues: configurationToFormValues({ ...configuration, ...configurationOverrides }),
    resolver: zodResolver(configurationFormSchema),
  })

  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <BusinessProfileFields />
        <button type="submit">Submit</button>
      </form>
    </FormProvider>
  )
}

function renderFields(props: Partial<React.ComponentProps<typeof Harness>> = {}) {
  const onSubmit = vi.fn()
  render(<Harness onSubmit={onSubmit} {...props} />)
  return { onSubmit }
}

describe('BusinessProfileFields', () => {
  it('renders every field US-6.1 asks for', () => {
    renderFields()
    expect(screen.getByLabelText('Business name')).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
    expect(screen.getByLabelText('Primary phone')).toBeInTheDocument()
    expect(screen.getByLabelText('Website')).toBeInTheDocument()
    expect(screen.getByLabelText('Time zone')).toBeInTheDocument()
    expect(screen.getByLabelText('Address')).toBeInTheDocument()
    expect(screen.getByLabelText('Locations')).toBeInTheDocument()
  })

  it('pre-fills from the shared form context', () => {
    renderFields()
    expect(screen.getByDisplayValue('Horizon Partners')).toBeInTheDocument()
    expect(screen.getByLabelText('Time zone')).toHaveValue('America/Chicago')
  })

  it('keeps a time zone that is not in the curated list selected instead of blanking it', () => {
    renderFields({
      configurationOverrides: {
        businessProfile: { ...configuration.businessProfile, timezone: 'Asia/Tokyo' },
      },
    })
    expect(screen.getByLabelText('Time zone')).toHaveValue('Asia/Tokyo')
  })

  it('shows all seven days, Sunday first', () => {
    renderFields()
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(8)
    expect(screen.getByRole('row', { name: /Sunday/ })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Saturday/ })).toBeInTheDocument()
  })

  it('disables the time inputs for a closed day', () => {
    renderFields()
    const sundayRow = screen.getByRole('row', { name: /Sunday/ })
    expect(within(sundayRow).getByLabelText('Opening time')).toBeDisabled()
  })

  it('enables the time inputs once a closed day is toggled open', async () => {
    const user = userEvent.setup()
    renderFields()
    const sundayRow = screen.getByRole('row', { name: /Sunday/ })
    await user.click(within(sundayRow).getByLabelText('Closed'))
    expect(within(sundayRow).getByLabelText('Opening time')).toBeEnabled()
  })

  it('submits under the businessProfile key when the whole form is valid', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFields()

    const name = screen.getByLabelText('Business name')
    await user.clear(name)
    await user.type(name, 'Meridian Partners')
    await user.click(screen.getByRole('button', { name: 'Submit' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          businessProfile: expect.objectContaining({ name: 'Meridian Partners' }),
        }),
        expect.anything(),
      ),
    )
  })

  it('shows a validation error and does not submit when the name is blank', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFields()

    const name = screen.getByLabelText('Business name')
    await user.clear(name)
    await user.click(screen.getByRole('button', { name: 'Submit' }))

    expect(await screen.findByText('Enter a business name')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
