import { zodResolver } from '@hookform/resolvers/zod'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm } from 'react-hook-form'

import type { ConciergeConfiguration } from '@/types'

import {
  configurationFormSchema,
  configurationToFormValues,
} from './configurationFormSchema'
import type { ConfigurationFormValues } from './configurationFormSchema'
import { TerminologyFields } from './TerminologyFields'

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
    supportedLanguages: ['en-US'],
  },
  terminology: {
    customer: 'Client',
    reservation: 'Appointment',
    location: 'Office',
    employee: 'Team member',
  },
  hasUnpublishedChanges: false,
}

function Harness({ onSubmit }: { onSubmit: (values: ConfigurationFormValues) => void }) {
  const form = useForm<ConfigurationFormValues>({
    defaultValues: configurationToFormValues(configuration),
    resolver: zodResolver(configurationFormSchema),
  })

  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <TerminologyFields />
        <button type="submit">Submit</button>
      </form>
    </FormProvider>
  )
}

function renderFields() {
  const onSubmit = vi.fn()
  render(<Harness onSubmit={onSubmit} />)
  return { onSubmit }
}

describe('TerminologyFields', () => {
  it('renders all four PRD §13.3 terms', () => {
    renderFields()
    expect(screen.getByLabelText(/What do you call a customer/)).toBeInTheDocument()
    expect(screen.getByLabelText(/What do you call a reservation/)).toBeInTheDocument()
    expect(screen.getByLabelText(/What do you call a location/)).toBeInTheDocument()
    expect(screen.getByLabelText(/What do you call an employee/)).toBeInTheDocument()
  })

  it('pre-fills from the shared form context', () => {
    renderFields()
    expect(screen.getByDisplayValue('Client')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Appointment')).toBeInTheDocument()
  })

  it('shows a validation error and does not submit when a term is blank', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFields()

    const customer = screen.getByLabelText(/What do you call a customer/)
    await user.clear(customer)
    await user.click(screen.getByRole('button', { name: 'Submit' }))

    expect(await screen.findByText('Enter what you call a customer')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits under the terminology key when the whole form is valid', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFields()

    const customer = screen.getByLabelText(/What do you call a customer/)
    await user.clear(customer)
    await user.type(customer, 'Member')
    await user.click(screen.getByRole('button', { name: 'Submit' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          terminology: expect.objectContaining({ customer: 'Member' }),
        }),
        expect.anything(),
      ),
    )
  })
})
