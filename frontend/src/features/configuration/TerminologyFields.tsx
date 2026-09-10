import { useFormContext } from 'react-hook-form'

import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'

import type { ConfigurationFormValues } from './configurationFormSchema'

/**
 * PRD §13.3 — the four nouns an organization can rename to match how it
 * actually talks about its business. The Terminology slice of the
 * Configuration page's single shared form (see `BusinessProfileFields` for
 * the same split rationale).
 */
export function TerminologyFields() {
  const {
    register,
    formState: { errors },
  } = useFormContext<ConfigurationFormValues>()

  const terminologyErrors = errors.terminology

  return (
    <div className="max-w-2xl space-y-1">
      <Field
        label="What do you call a customer?"
        htmlFor="customer"
        description="e.g. Customers, Clients, Members, Guests"
        error={terminologyErrors?.customer?.message}
      >
        <Input {...register('terminology.customer')} />
      </Field>

      <Field
        label="What do you call a reservation?"
        htmlFor="reservation"
        description="e.g. Reservations, Appointments, Bookings"
        error={terminologyErrors?.reservation?.message}
      >
        <Input {...register('terminology.reservation')} />
      </Field>

      <Field
        label="What do you call a location?"
        htmlFor="location"
        description="e.g. Locations, Branches, Offices"
        error={terminologyErrors?.location?.message}
      >
        <Input {...register('terminology.location')} />
      </Field>

      <Field
        label="What do you call an employee?"
        htmlFor="employee"
        description="e.g. Employees, Associates, Team members"
        error={terminologyErrors?.employee?.message}
      >
        <Input {...register('terminology.employee')} />
      </Field>
    </div>
  )
}
