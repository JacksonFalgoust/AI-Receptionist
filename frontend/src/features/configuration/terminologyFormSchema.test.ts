import { describe, expect, it } from 'vitest'

import type { Terminology } from '@/types'

import {
  formValuesToTerminology,
  terminologyFormSchema,
  terminologyToFormValues,
} from './terminologyFormSchema'
import type { TerminologyFormValues } from './terminologyFormSchema'

const baseValues: TerminologyFormValues = {
  customer: 'Client',
  reservation: 'Appointment',
  location: 'Office',
  employee: 'Team member',
}

const baseTerminology: Terminology = {
  customer: 'Client',
  reservation: 'Appointment',
  location: 'Office',
  employee: 'Team member',
}

describe('terminologyFormSchema', () => {
  const schema = terminologyFormSchema

  it('requires a term for customer', () => {
    expect(schema.safeParse({ ...baseValues, customer: '' }).success).toBe(false)
  })

  it('requires a term for reservation', () => {
    expect(schema.safeParse({ ...baseValues, reservation: '' }).success).toBe(false)
  })

  it('requires a term for location', () => {
    expect(schema.safeParse({ ...baseValues, location: '' }).success).toBe(false)
  })

  it('requires a term for employee', () => {
    expect(schema.safeParse({ ...baseValues, employee: '' }).success).toBe(false)
  })

  it('accepts a fully valid set of terms', () => {
    expect(schema.safeParse(baseValues).success).toBe(true)
  })
})

describe('terminologyToFormValues', () => {
  it('carries the fields across unchanged', () => {
    expect(terminologyToFormValues(baseTerminology)).toEqual(baseValues)
  })
})

describe('formValuesToTerminology', () => {
  it('trims each term', () => {
    const terminology = formValuesToTerminology({ ...baseValues, customer: '  Client  ' })
    expect(terminology.customer).toBe('Client')
  })
})
