import { describe, expect, it } from 'vitest'

import type { ConciergeIdentity } from '@/types'

import {
  formValuesToIdentity,
  identityFormSchema,
  identityToFormValues,
} from './identityFormSchema'
import type { IdentityFormValues } from './identityFormSchema'

const baseValues: IdentityFormValues = {
  name: 'Horizon Concierge',
  greeting: 'Thanks for contacting Horizon Partners.',
  closing: 'Thanks for your time.',
  voice: 'Avery — Warm',
  tone: 'friendly',
  customTone: '',
  primaryLanguage: 'en-US',
  supportedLanguages: ['en-US', 'es-US'],
}

const baseIdentity: ConciergeIdentity = {
  name: 'Horizon Concierge',
  greeting: 'Thanks for contacting Horizon Partners.',
  closing: 'Thanks for your time.',
  voice: 'Avery — Warm',
  tone: 'friendly',
  primaryLanguage: 'en-US',
  supportedLanguages: ['en-US', 'es-US'],
}

describe('identityFormSchema', () => {
  const schema = identityFormSchema

  it('requires a Concierge name', () => {
    expect(schema.safeParse({ ...baseValues, name: '' }).success).toBe(false)
  })

  it('requires a greeting', () => {
    expect(schema.safeParse({ ...baseValues, greeting: '' }).success).toBe(false)
  })

  it('requires a closing message', () => {
    expect(schema.safeParse({ ...baseValues, closing: '' }).success).toBe(false)
  })

  it('requires a voice', () => {
    expect(schema.safeParse({ ...baseValues, voice: '' }).success).toBe(false)
  })

  it('requires a tone', () => {
    expect(schema.safeParse({ ...baseValues, tone: '' }).success).toBe(false)
  })

  it('requires a description when tone is custom', () => {
    const result = schema.safeParse({ ...baseValues, tone: 'custom', customTone: '' })
    expect(result.success).toBe(false)
  })

  it('accepts a custom tone once described', () => {
    const result = schema.safeParse({
      ...baseValues,
      tone: 'custom',
      customTone: 'Warm but concise',
    })
    expect(result.success).toBe(true)
  })

  it('requires a primary language', () => {
    expect(schema.safeParse({ ...baseValues, primaryLanguage: '' }).success).toBe(false)
  })

  it('requires at least one supported language', () => {
    expect(schema.safeParse({ ...baseValues, supportedLanguages: [] }).success).toBe(false)
  })

  it('requires the primary language to be among the supported languages', () => {
    const result = schema.safeParse({
      ...baseValues,
      primaryLanguage: 'fr-CA',
      supportedLanguages: ['en-US'],
    })
    expect(result.success).toBe(false)
  })

  it('accepts a fully valid identity', () => {
    expect(schema.safeParse(baseValues).success).toBe(true)
  })
})

describe('identityToFormValues', () => {
  it('carries the plain fields across unchanged', () => {
    const values = identityToFormValues(baseIdentity)
    expect(values.name).toBe('Horizon Concierge')
    expect(values.voice).toBe('Avery — Warm')
    expect(values.tone).toBe('friendly')
    expect(values.supportedLanguages).toEqual(['en-US', 'es-US'])
  })

  it('leaves customTone blank when the identity has none', () => {
    expect(identityToFormValues(baseIdentity).customTone).toBe('')
  })

  it('carries an existing custom tone description across', () => {
    const values = identityToFormValues({
      ...baseIdentity,
      tone: 'custom',
      customTone: 'Warm but concise',
    })
    expect(values.customTone).toBe('Warm but concise')
  })
})

describe('formValuesToIdentity', () => {
  it('trims text fields', () => {
    const identity = formValuesToIdentity({ ...baseValues, name: '  Horizon Concierge  ' })
    expect(identity.name).toBe('Horizon Concierge')
  })

  it('omits customTone when the tone is not custom', () => {
    const identity = formValuesToIdentity({ ...baseValues, tone: 'friendly', customTone: 'Ignored' })
    expect(identity.customTone).toBeUndefined()
  })

  it('carries a custom tone description across when the tone is custom', () => {
    const identity = formValuesToIdentity({
      ...baseValues,
      tone: 'custom',
      customTone: 'Warm but concise',
    })
    expect(identity.customTone).toBe('Warm but concise')
  })
})
