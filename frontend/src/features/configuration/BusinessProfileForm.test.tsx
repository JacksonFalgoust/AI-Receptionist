import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { BusinessProfile } from '@/types'

import { BusinessProfileForm } from './BusinessProfileForm'
import { profileToFormValues } from './businessProfileFormSchema'

const profile: BusinessProfile = {
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
}

function renderForm(props: Partial<React.ComponentProps<typeof BusinessProfileForm>> = {}) {
  const onSubmit = vi.fn()
  render(
    <BusinessProfileForm
      defaultValues={profileToFormValues(profile)}
      submitLabel="Save changes"
      onSubmit={onSubmit}
      {...props}
    />,
  )
  return { onSubmit }
}

describe('BusinessProfileForm', () => {
  it('renders every field US-6.1 asks for', () => {
    renderForm()
    expect(screen.getByLabelText('Business name')).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
    expect(screen.getByLabelText('Primary phone')).toBeInTheDocument()
    expect(screen.getByLabelText('Website')).toBeInTheDocument()
    expect(screen.getByLabelText('Time zone')).toBeInTheDocument()
    expect(screen.getByLabelText('Address')).toBeInTheDocument()
    expect(screen.getByLabelText('Locations')).toBeInTheDocument()
  })

  it('shows all seven days, Sunday first', () => {
    renderForm()
    const rows = screen.getAllByRole('row')
    // Header row, plus seven day rows.
    expect(rows).toHaveLength(8)
    expect(screen.getByRole('row', { name: /Sunday/ })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Saturday/ })).toBeInTheDocument()
  })

  it('pre-fills a closed day as closed, with no times to enter', () => {
    renderForm()
    const sundayRow = screen.getByRole('row', { name: /Sunday/ })
    expect(within(sundayRow).getByLabelText('Closed')).toBeChecked()
  })

  it('disables the time inputs for a closed day', () => {
    renderForm()
    const sundayRow = screen.getByRole('row', { name: /Sunday/ })
    expect(within(sundayRow).getByLabelText('Opening time')).toBeDisabled()
    expect(within(sundayRow).getByLabelText('Closing time')).toBeDisabled()
  })

  it('enables the time inputs once a closed day is toggled open', async () => {
    const user = userEvent.setup()
    renderForm()
    const sundayRow = screen.getByRole('row', { name: /Sunday/ })
    await user.click(within(sundayRow).getByLabelText('Closed'))
    expect(within(sundayRow).getByLabelText('Opening time')).toBeEnabled()
  })

  it('shows a validation error and does not submit when the name is blank', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    const name = screen.getByLabelText('Business name')
    await user.clear(name)
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Enter a business name')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits parsed values when the form is valid', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    const name = screen.getByLabelText('Business name')
    await user.clear(name)
    await user.type(name, 'Meridian Partners')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Meridian Partners' }),
        expect.anything(),
      ),
    )
  })

  it('disables the submit button while a save is in flight', () => {
    renderForm({ isSubmitting: true })
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
  })
})
