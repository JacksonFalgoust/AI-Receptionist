import { z } from 'zod'

import type { BusinessHours, BusinessProfile } from '@/types'

/** `BusinessHours.day` is `0 = Sunday`; this is that same order, spelled out for display. */
export const DAY_LABELS = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
] as const

export interface DayHoursFormValues {
  closed: boolean
  /** `HH:MM`, or `''` for a closed day. */
  open: string
  close: string
}

export interface BusinessProfileFormValues {
  name: string
  description: string
  phone: string
  website: string
  timezone: string
  address: string
  locations: string
  /** Always seven entries, index === `BusinessHours.day`. */
  hours: DayHoursFormValues[]
}

const dayHoursSchema = z.object({
  closed: z.boolean(),
  open: z.string(),
  close: z.string(),
})

export const businessProfileFormSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter a business name'),
    description: z.string(),
    phone: z.string().trim().min(1, 'Enter a phone number'),
    website: z.string(),
    timezone: z.string().trim().min(1, 'Select a time zone'),
    address: z.string().trim().min(1, 'Enter an address'),
    locations: z.string(),
    hours: z.array(dayHoursSchema).length(7),
  })
  .superRefine((values, ctx) => {
    if (values.website.trim() !== '' && !z.url().safeParse(values.website.trim()).success) {
      ctx.addIssue({ code: 'custom', path: ['website'], message: 'Enter a valid web address' })
    }

    values.hours.forEach((day, index) => {
      if (day.closed) return

      if (day.open.trim() === '') {
        ctx.addIssue({
          code: 'custom',
          path: ['hours', index, 'open'],
          message: 'Enter an opening time',
        })
      }
      if (day.close.trim() === '') {
        ctx.addIssue({
          code: 'custom',
          path: ['hours', index, 'close'],
          message: 'Enter a closing time',
        })
      }
      if (day.open.trim() !== '' && day.close.trim() !== '' && day.close <= day.open) {
        ctx.addIssue({
          code: 'custom',
          path: ['hours', index, 'close'],
          message: 'Closing time must be after opening time',
        })
      }
    })
  })

/** An existing profile's fields, laid out as the form's controls expect them. */
export function profileToFormValues(profile: BusinessProfile): BusinessProfileFormValues {
  const byDay = new Map(profile.hours.map((entry) => [entry.day, entry]))

  return {
    name: profile.name,
    description: profile.description,
    phone: profile.phone,
    website: profile.website,
    timezone: profile.timezone,
    address: profile.address,
    locations: profile.locations,
    hours: DAY_LABELS.map((_, day) => {
      const entry = byDay.get(day)
      return {
        closed: entry?.closed ?? true,
        open: entry?.open ?? '',
        close: entry?.close ?? '',
      }
    }),
  }
}

/** The submitted form, turned into what `conciergeService.saveDraft` expects. */
export function formValuesToProfile(values: BusinessProfileFormValues): BusinessProfile {
  const hours: BusinessHours[] = values.hours.map((day, index) =>
    day.closed
      ? { day: index, closed: true }
      : { day: index, open: day.open, close: day.close, closed: false },
  )

  return {
    name: values.name.trim(),
    description: values.description.trim(),
    phone: values.phone.trim(),
    website: values.website.trim(),
    timezone: values.timezone.trim(),
    address: values.address.trim(),
    locations: values.locations.trim(),
    hours,
  }
}
