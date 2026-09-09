import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { TIMEZONE_OPTIONS } from '@/lib/timezones'

import { businessProfileFormSchema, DAY_LABELS } from './businessProfileFormSchema'
import type { BusinessProfileFormValues } from './businessProfileFormSchema'

export interface BusinessProfileFormProps {
  defaultValues: BusinessProfileFormValues
  isSubmitting?: boolean
  submitLabel: string
  onSubmit: (values: BusinessProfileFormValues) => void
}

/**
 * US-6.1's business profile fields. Purely presentational — `ConfigurationPage`
 * owns the service call, the toast, and the query cache — so this stays easy
 * to test in isolation, the same split `KnowledgeForm`/`KnowledgeEditorPage` use.
 */
export function BusinessProfileForm({
  defaultValues,
  isSubmitting = false,
  submitLabel,
  onSubmit,
}: BusinessProfileFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<BusinessProfileFormValues>({
    defaultValues,
    resolver: zodResolver(businessProfileFormSchema),
  })

  const hours = watch('hours')

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="max-w-2xl space-y-1">
      <Field label="Business name" htmlFor="name" error={errors.name?.message}>
        <Input {...register('name')} />
      </Field>

      <Field label="Description" htmlFor="description">
        <Textarea rows={3} {...register('description')} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Primary phone" htmlFor="phone" error={errors.phone?.message}>
          <Input type="tel" {...register('phone')} />
        </Field>
        <Field label="Website" htmlFor="website" error={errors.website?.message}>
          <Input type="url" placeholder="https://example.com" {...register('website')} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Time zone" htmlFor="timezone" error={errors.timezone?.message}>
          <Select
            {...register('timezone')}
            options={TIMEZONE_OPTIONS}
            placeholder="Select a time zone"
          />
        </Field>
        <Field label="Locations" htmlFor="locations">
          <Input {...register('locations')} />
        </Field>
      </div>

      <Field label="Address" htmlFor="address" error={errors.address?.message}>
        <Input {...register('address')} />
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
                const closed = hours[index]?.closed ?? false
                const openError = errors.hours?.[index]?.open?.message
                const closeError = errors.hours?.[index]?.close?.message
                return (
                  <tr key={label} className="border-b border-border last:border-b-0">
                    <th scope="row" className="px-3 py-2 text-left font-medium text-ink">
                      {label}
                    </th>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label="Closed"
                        {...register(`hours.${index}.closed`)}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="time"
                        aria-label="Opening time"
                        aria-invalid={Boolean(openError)}
                        disabled={closed}
                        className="rounded-sm border border-border bg-surface px-2 py-1 text-sm disabled:opacity-50"
                        {...register(`hours.${index}.open`)}
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
                        {...register(`hours.${index}.close`)}
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

      <Button type="submit" isLoading={isSubmitting} className="mt-2">
        {submitLabel}
      </Button>
    </form>
  )
}
