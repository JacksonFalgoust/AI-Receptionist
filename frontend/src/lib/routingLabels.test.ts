import { describe, expect, it } from 'vitest'

import {
  ESCALATION_CONDITIONS,
  ROUTING_DESTINATION_TYPES,
  ROUTING_SCHEDULES,
  conditionDetailLabel,
  destinationValueLabel,
  escalationConditionLabel,
  routingDestinationLabel,
  routingScheduleLabel,
} from './routingLabels'

describe('routingLabels', () => {
  it('covers all ten PRD §18.1 conditions', () => {
    expect(ESCALATION_CONDITIONS).toHaveLength(10)
  })

  it('covers all six PRD §18.2 destination types', () => {
    expect(ROUTING_DESTINATION_TYPES).toHaveLength(6)
  })

  it('covers every schedule, including the always-on case', () => {
    expect(ROUTING_SCHEDULES).toHaveLength(5)
    expect(ROUTING_SCHEDULES).toContain('always')
  })

  it('names every value in business language, never as a token', () => {
    for (const condition of ESCALATION_CONDITIONS) {
      const label = escalationConditionLabel(condition)
      expect(label.trim()).not.toBe('')
      expect(label).not.toContain('_')
    }
    for (const type of ROUTING_DESTINATION_TYPES) {
      expect(routingDestinationLabel(type)).not.toContain('_')
      expect(destinationValueLabel(type).trim()).not.toBe('')
    }
    for (const schedule of ROUTING_SCHEDULES) {
      expect(routingScheduleLabel(schedule)).not.toContain('_')
    }
  })

  it('reads a condition the way a person would say it', () => {
    expect(escalationConditionLabel('customer_requests_person')).toBe('Customer asks for a person')
    expect(routingDestinationLabel('phone_number')).toBe('Phone number')
    expect(routingScheduleLabel('after_hours')).toBe('After hours')
  })

  it('asks for a detail on exactly the conditions that mean nothing without one', () => {
    expect(conditionDetailLabel('keyword_match')).toBe('Keywords')
    expect(conditionDetailLabel('transaction_over_threshold')).toBe('Amount threshold')
    expect(conditionDetailLabel('complaint')).toBeUndefined()
    expect(conditionDetailLabel('vip_customer')).toBeUndefined()
  })

  it('labels the destination value for what it actually is', () => {
    expect(destinationValueLabel('employee')).toBe('Employee name')
    expect(destinationValueLabel('phone_number')).toBe('Phone number')
  })
})
