import { describe, expect, it } from 'vitest'

import type { RoutingRule } from '@/types'

import {
  formValuesToInput,
  routingRuleFormSchema,
  ruleToFormValues,
} from './routingRuleFormSchema'

const rule: RoutingRule = {
  id: 'rr_test',
  organizationId: 'org_test',
  name: 'Priority client keywords',
  condition: 'keyword_match',
  conditionDetail: 'urgent, deadline',
  destination: { type: 'department', value: 'Advisory' },
  schedule: 'always',
  priority: 7,
  enabled: false,
}

function valid() {
  return ruleToFormValues(rule)
}

describe('routingRuleFormSchema', () => {
  it('flattens a rule into the shape the form edits', () => {
    expect(ruleToFormValues(rule)).toEqual({
      name: 'Priority client keywords',
      condition: 'keyword_match',
      conditionDetail: 'urgent, deadline',
      destinationType: 'department',
      destinationValue: 'Advisory',
      schedule: 'always',
      priority: 7,
      enabled: false,
    })
  })

  it('starts a new rule enabled, at the priority it is handed', () => {
    const values = ruleToFormValues(undefined, 9)
    expect(values.name).toBe('')
    expect(values.conditionDetail).toBe('')
    expect(values.priority).toBe(9)
    expect(values.enabled).toBe(true)
  })

  it('accepts a complete rule', () => {
    expect(routingRuleFormSchema.safeParse(valid()).success).toBe(true)
  })

  it('requires a name', () => {
    const result = routingRuleFormSchema.safeParse({ ...valid(), name: '  ' })
    expect(result.success).toBe(false)
  })

  it('requires somewhere to send the escalation', () => {
    const result = routingRuleFormSchema.safeParse({ ...valid(), destinationValue: '' })
    expect(result.success).toBe(false)
  })

  it('requires a priority of at least one', () => {
    expect(routingRuleFormSchema.safeParse({ ...valid(), priority: 0 }).success).toBe(false)
    expect(routingRuleFormSchema.safeParse({ ...valid(), priority: 1.5 }).success).toBe(false)
  })

  it('requires the detail on a condition that means nothing without one', () => {
    const result = routingRuleFormSchema.safeParse({ ...valid(), conditionDetail: '' })
    expect(result.success).toBe(false)
  })

  it('does not demand a detail from a condition that needs none', () => {
    const result = routingRuleFormSchema.safeParse({
      ...valid(),
      condition: 'complaint',
      conditionDetail: '',
    })
    expect(result.success).toBe(true)
  })

  it('builds the service input, nesting the destination back together', () => {
    expect(formValuesToInput(valid())).toEqual({
      name: 'Priority client keywords',
      condition: 'keyword_match',
      conditionDetail: 'urgent, deadline',
      destination: { type: 'department', value: 'Advisory' },
      schedule: 'always',
      priority: 7,
      enabled: false,
    })
  })

  it('drops a detail left behind by a condition that no longer takes one', () => {
    const input = formValuesToInput({ ...valid(), condition: 'complaint' })
    expect(input.conditionDetail).toBeUndefined()
  })
})
