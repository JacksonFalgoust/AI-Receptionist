import { describe, expect, it } from 'vitest'

import type { BusinessProfile } from '@/types'

import {
  businessProfileFormSchema,
  DAY_LABELS,
  formValuesToProfile,
  profileToFormValues,
} from './businessProfileFormSchema'
import type { BusinessProfileFormValues } from './businessProfileFormSchema'

function closedDay() {
  return { closed: true, open: '', close: '' }
}

function openDay(open = '08:30', close = '17:30') {
  return { closed: false, open, close }
}

const baseValues: BusinessProfileFormValues = {
  name: 'Horizon Partners',
  description: 'A professional services firm.',
  phone: '+1 555 0100',
  website: 'https://horizonpartners.example.com',
  timezone: 'America/Chicago',
  address: '1200 Meridian Way, Suite 400',
  locations: '3 locations',
  hours: [closedDay(), openDay(), openDay(), openDay(), openDay(), openDay(), closedDay()],
}

const baseProfile: BusinessProfile = {
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
    { day: 5, open: '08:30', close: '17:30', closed: false },
    { day: 6, closed: true },
  ],
}

describe('businessProfileFormSchema', () => {
  const schema = businessProfileFormSchema

  it('requires a business name', () => {
    expect(schema.safeParse({ ...baseValues, name: '' }).success).toBe(false)
  })

  it('requires a phone number', () => {
    expect(schema.safeParse({ ...baseValues, phone: '' }).success).toBe(false)
  })

  it('requires an address', () => {
    expect(schema.safeParse({ ...baseValues, address: '' }).success).toBe(false)
  })

  it('requires a time zone', () => {
    expect(schema.safeParse({ ...baseValues, timezone: '' }).success).toBe(false)
  })

  it('accepts a blank website — not every business has one', () => {
    expect(schema.safeParse({ ...baseValues, website: '' }).success).toBe(true)
  })

  it('rejects a website that is not a valid URL', () => {
    expect(schema.safeParse({ ...baseValues, website: 'not a url' }).success).toBe(false)
  })

  it('requires an opening time for a day that is not closed', () => {
    const result = schema.safeParse({
      ...baseValues,
      hours: [closedDay(), { closed: false, open: '', close: '17:30' }, ...baseValues.hours.slice(2)],
    })
    expect(result.success).toBe(false)
  })

  it('requires a closing time for a day that is not closed', () => {
    const result = schema.safeParse({
      ...baseValues,
      hours: [closedDay(), { closed: false, open: '08:30', close: '' }, ...baseValues.hours.slice(2)],
    })
    expect(result.success).toBe(false)
  })

  it('rejects a closing time at or before the opening time', () => {
    const result = schema.safeParse({
      ...baseValues,
      hours: [closedDay(), openDay('09:00', '09:00'), ...baseValues.hours.slice(2)],
    })
    expect(result.success).toBe(false)
  })

  it('allows a closed day to leave its times blank', () => {
    expect(schema.safeParse({ ...baseValues, hours: baseValues.hours }).success).toBe(true)
  })

  it('accepts a fully valid profile', () => {
    expect(schema.safeParse(baseValues).success).toBe(true)
  })
})

describe('profileToFormValues', () => {
  it('carries the plain fields across unchanged', () => {
    const values = profileToFormValues(baseProfile)
    expect(values.name).toBe('Horizon Partners')
    expect(values.phone).toBe('+1 555 0100')
    expect(values.website).toBe('https://horizonpartners.example.com')
    expect(values.timezone).toBe('America/Chicago')
    expect(values.address).toBe('1200 Meridian Way, Suite 400')
    expect(values.locations).toBe('3 locations')
  })

  it('maps a closed day to a blank open/close pair', () => {
    const values = profileToFormValues(baseProfile)
    expect(values.hours[0]).toEqual({ closed: true, open: '', close: '' })
  })

  it('maps an open day across in order', () => {
    const values = profileToFormValues(baseProfile)
    expect(values.hours[1]).toEqual({ closed: false, open: '08:30', close: '17:30' })
  })

  it('always produces seven rows, Sunday first', () => {
    expect(profileToFormValues(baseProfile).hours).toHaveLength(7)
    expect(DAY_LABELS[0]).toBe('Sunday')
    expect(DAY_LABELS).toHaveLength(7)
  })
})

describe('formValuesToProfile', () => {
  it('trims text fields', () => {
    const profile = formValuesToProfile({ ...baseValues, name: '  Horizon Partners  ' })
    expect(profile.name).toBe('Horizon Partners')
  })

  it('turns a closed row into a BusinessHours entry with no times', () => {
    const profile = formValuesToProfile(baseValues)
    expect(profile.hours[0]).toEqual({ day: 0, closed: true })
  })

  it('turns an open row into a BusinessHours entry with its times', () => {
    const profile = formValuesToProfile(baseValues)
    expect(profile.hours[1]).toEqual({ day: 1, open: '08:30', close: '17:30', closed: false })
  })

  it('round-trips through profileToFormValues without changing the hours', () => {
    const roundTripped = formValuesToProfile(profileToFormValues(baseProfile))
    expect(roundTripped.hours).toEqual(baseProfile.hours)
  })
})
