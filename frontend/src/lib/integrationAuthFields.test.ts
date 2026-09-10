import { describe, expect, it } from 'vitest'

import { INTEGRATION_CATEGORIES } from './integrationLabels'
import {
  ACCOUNT_LABEL_FIELD,
  INTEGRATION_AUTH_FIELDS,
  integrationAuthFields,
} from './integrationAuthFields'

describe('integrationAuthFields', () => {
  it('covers every integration category', () => {
    expect(Object.keys(INTEGRATION_AUTH_FIELDS).sort()).toEqual([...INTEGRATION_CATEGORIES].sort())
  })

  it('asks every category for at least one field', () => {
    for (const category of INTEGRATION_CATEGORIES) {
      expect(integrationAuthFields(category).length).toBeGreaterThan(0)
    }
  })

  it('collects at least one secret per category, so nothing connects on public data alone', () => {
    for (const category of INTEGRATION_CATEGORIES) {
      expect(integrationAuthFields(category).some((field) => field.type === 'secret')).toBe(true)
    }
  })

  it('never repeats a field name inside a category', () => {
    for (const category of INTEGRATION_CATEGORIES) {
      const names = integrationAuthFields(category).map((field) => field.name)
      expect(new Set(names).size).toBe(names.length)
    }
  })

  it('never reuses the account-label name, which would collide with the universal field', () => {
    for (const category of INTEGRATION_CATEGORIES) {
      const names = integrationAuthFields(category).map((field) => field.name)
      expect(names).not.toContain(ACCOUNT_LABEL_FIELD.name)
    }
  })

  it('labels every field', () => {
    for (const category of INTEGRATION_CATEGORIES) {
      for (const field of integrationAuthFields(category)) {
        expect(field.label.trim()).not.toBe('')
      }
    }
  })
})
