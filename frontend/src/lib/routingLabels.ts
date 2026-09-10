import type { EscalationCondition, RoutingDestinationType, RoutingSchedule } from '@/types'

/**
 * PRD §18.1's ten escalation conditions, named as the business names them
 * (PRD §3.1). Exhaustive `Record`s throughout this file, so a new union member
 * is a compile error here until it is given a label — the same guarantee
 * `integrationLabels.ts` gives categories.
 */
export const ESCALATION_CONDITION_LABELS: Record<EscalationCondition, string> = {
  customer_requests_person: 'Customer asks for a person',
  cannot_answer: 'Concierge cannot answer',
  frustration_detected: 'Customer frustration detected',
  complaint: 'Complaint received',
  refund_requested: 'Refund requested',
  transaction_over_threshold: 'Transaction over threshold',
  vip_customer: 'VIP customer',
  keyword_match: 'Specific keywords heard',
  workflow_failure: 'Workflow failure',
  integration_unavailable: 'Business system unavailable',
}

/** PRD §18.2. */
export const ROUTING_DESTINATION_LABELS: Record<RoutingDestinationType, string> = {
  employee: 'Employee',
  team: 'Team',
  department: 'Department',
  queue: 'Queue',
  phone_number: 'Phone number',
  external_system: 'External system',
}

/** PRD §18.3, plus `always` for a rule that ignores the calendar. */
export const ROUTING_SCHEDULE_LABELS: Record<RoutingSchedule, string> = {
  always: 'Always',
  open_hours: 'Open hours',
  after_hours: 'After hours',
  weekends: 'Weekends',
  holidays: 'Holidays',
}

/**
 * What the destination's free-text value actually holds, which depends
 * entirely on its type — "Employee name" for a person, "Phone number" for a
 * number. Used as the editor's field label so the input never reads just
 * "Value".
 */
export const DESTINATION_VALUE_LABELS: Record<RoutingDestinationType, string> = {
  employee: 'Employee name',
  team: 'Team name',
  department: 'Department name',
  queue: 'Queue name',
  phone_number: 'Phone number',
  external_system: 'System name',
}

/**
 * Conditions whose label means nothing on its own — a threshold with no
 * amount, a keyword match with no keywords. `RoutingRule.conditionDetail`
 * carries the value; every other condition leaves it unset.
 */
export const CONDITION_DETAIL_LABELS: Partial<Record<EscalationCondition, string>> = {
  keyword_match: 'Keywords',
  transaction_over_threshold: 'Amount threshold',
}

// Derived from the label records rather than listed a second time: a
// hand-kept array compiles cleanly while silently omitting a newly added
// member from every select in the app. `Object.keys` preserves declaration
// order, so these records are also the option order.
export const ESCALATION_CONDITIONS = Object.keys(
  ESCALATION_CONDITION_LABELS,
) as EscalationCondition[]
export const ROUTING_DESTINATION_TYPES = Object.keys(
  ROUTING_DESTINATION_LABELS,
) as RoutingDestinationType[]
export const ROUTING_SCHEDULES = Object.keys(ROUTING_SCHEDULE_LABELS) as RoutingSchedule[]

export function escalationConditionLabel(condition: EscalationCondition): string {
  return ESCALATION_CONDITION_LABELS[condition]
}

export function routingDestinationLabel(type: RoutingDestinationType): string {
  return ROUTING_DESTINATION_LABELS[type]
}

export function routingScheduleLabel(schedule: RoutingSchedule): string {
  return ROUTING_SCHEDULE_LABELS[schedule]
}

export function destinationValueLabel(type: RoutingDestinationType): string {
  return DESTINATION_VALUE_LABELS[type]
}

export function conditionDetailLabel(condition: EscalationCondition): string | undefined {
  return CONDITION_DETAIL_LABELS[condition]
}
