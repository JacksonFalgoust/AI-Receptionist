import { useFormContext } from 'react-hook-form'

import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { withCurrentValue } from '@/lib/selectOptions'
import { TIMEZONE_OPTIONS } from '@/lib/timezones'

import { DAY_LABELS } from './businessProfileFormSchema'
import type { ConfigurationFormValues } from './configurationFormSchema'

/**
 * US-6.1's business profile fields — one slice of the Configuration page's
 * single shared form (see `configurationFormSchema.ts`). Reads and writes
 * through `useFormContext` under the `businessProfile` key rather than
 * owning a form of its own, so it saves and publishes together with Identity
 * and Terminology under one Save Draft / Publish pair.
 */
export function BusinessProfileFields() {
  const {
    register,
    watch,
    formState: { errors },
  } = useFormContext<ConfigurationFormValues>()

  const hours = watch('businessProfile.hours')
  const timezone = watch('businessProfile.timezone')
  const businessProfileErrors = errors.businessProfile

  return (
    <div className="max-w-2xl space-y-1">
      <Field label="Business name" htmlFor="name" error={businessProfileErrors?.name?.message}>
        <Input {...register('businessProfile.name')} />
      </Field>

      <Field label="Description" htmlFor="description">
        <Textarea rows={3} {...register('businessProfile.description')} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Primary phone"
          htmlFor="phone"
          error={businessProfileErrors?.phone?.message}
        >
          <Input type="tel" {...register('businessProfile.phone')} />
        </Field>
        <Field label="Website" htmlFor="website" error={businessProfileErrors?.website?.message}>
          <Input type="url" placeholder="https://example.com" {...register('businessProfile.website')} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Time zone"
          htmlFor="timezone"
          error={businessProfileErrors?.timezone?.message}
        >
          <Select
            {...register('businessProfile.timezone')}
            options={withCurrentValue(TIMEZONE_OPTIONS, timezone)}
            placeholder="Select a time zone"
          />
        </Field>
        <Field label="Locations" htmlFor="locations">
          <Input {...register('businessProfile.locations')} />
        </Field>
      </div>

      <Field label="Address" htmlFor="address" error={businessProfileErrors?.address?.message}>
        <Input {...register('businessProfile.address')} />
      </Field>

      <fieldset className="mb-4">
        <legend className="mb-1.5 block text-sm font-semibold text-ink">Business hours</legend>
        <div className="overflow-x-auto rounded-sm border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface text-left text-xs font-semibold text-ink-secondary">
                <th scope="col" className="px-3 py-2">
                  Day
                </th>
                <th scope="col" className="px-3 py-2">
                  Closed
                </th>
                <th scope="col" className="px-3 py-2">
                  Opens
                </th>
                <th scope="col" className="px-3 py-2">
                  Closes
                </th>
              </tr>
            </thead>
            <tbody>
              {DAY_LABELS.map((label, index) => {
                const closed = hours?.[index]?.closed ?? false
                const dayErrors = businessProfileErrors?.hours?.[index]
                const openError = dayErrors?.open?.message
                const closeError = dayErrors?.close?.message
                return (
                  <tr key={label} className="border-b border-border last:border-b-0">
                    <th scope="row" className="px-3 py-2 text-left font-medium text-ink">
                      {label}
                    </th>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label="Closed"
                        {...register(`businessProfile.hours.${index}.closed`)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="time"
                        aria-label="Opening time"
                        aria-invalid={Boolean(openError)}
                        disabled={closed}
                        className="rounded-sm border border-border bg-surface px-2 py-1 text-sm disabled:opacity-50"
                        {...register(`businessProfile.hours.${index}.open`)}
                      />
                      {openError ? <p className="mt-1 text-xs text-danger">{openError}</p> : null}
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="time"
                        aria-label="Closing time"
                        aria-invalid={Boolean(closeError)}
                        disabled={closed}
                        className="rounded-sm border border-border bg-surface px-2 py-1 text-sm disabled:opacity-50"
                        {...register(`businessProfile.hours.${index}.close`)}
                      />
                      {closeError ? (
                        <p className="mt-1 text-xs text-danger">{closeError}</p>
                      ) : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </fieldset>
    </div>
  )
}
