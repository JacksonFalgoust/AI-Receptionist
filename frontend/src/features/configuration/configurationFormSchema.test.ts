import { describe, expect, it } from 'vitest'

import type { ConciergeConfiguration } from '@/types'

import {
  configurationFormSchema,
  configurationToFormValues,
  formValuesToPatch,
} from './configurationFormSchema'
import type { ConfigurationFormValues } from './configurationFormSchema'

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
      { day: 5, open: '08:30', close: '17:30', closed: false },
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

const validValues: ConfigurationFormValues = configurationToFormValues(configuration)

describe('configurationFormSchema', () => {
  it('accepts a fully valid configuration', () => {
    expect(configurationFormSchema.safeParse(validValues).success).toBe(true)
  })

  it('rejects an invalid business profile section', () => {
    const result = configurationFormSchema.safeParse({
      ...validValues,
      businessProfile: { ...validValues.businessProfile, name: '' },
    })
    expect(result.success).toBe(false)
  })

  it('rejects an invalid identity section', () => {
    const result = configurationFormSchema.safeParse({
      ...validValues,
      identity: { ...validValues.identity, tone: '' },
    })
    expect(result.success).toBe(false)
  })

  it('rejects an invalid terminology section', () => {
    const result = configurationFormSchema.safeParse({
      ...validValues,
      terminology: { ...validValues.terminology, customer: '' },
    })
    expect(result.success).toBe(false)
  })
})

describe('configurationToFormValues', () => {
  it('composes all three sections', () => {
    const values = configurationToFormValues(configuration)
    expect(values.businessProfile.name).toBe('Horizon Partners')
    expect(values.identity.name).toBe('Horizon Concierge')
    expect(values.terminology.customer).toBe('Client')
  })
})

describe('formValuesToPatch', () => {
  it('composes all three sections into a saveDraft patch', () => {
    const patch = formValuesToPatch(validValues)
    expect(patch.businessProfile?.name).toBe('Horizon Partners')
    expect(patch.identity?.name).toBe('Horizon Concierge')
    expect(patch.terminology?.customer).toBe('Client')
  })
})
