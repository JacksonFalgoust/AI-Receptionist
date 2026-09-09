import type { RoutingRule } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

/**
 * PRD §18: conditions, destinations, and schedules all drawn from the unions.
 * The base array is annotated so `.map()` does not widen them to `string`.
 */
const ROUTING_RULES: Omit<RoutingRule, 'organizationId'>[] = [
  { id: 'rr_0001', name: 'Client asks for a person', condition: 'customer_requests_person', destination: { type: 'queue', value: 'Client care queue' }, schedule: 'open_hours', priority: 1, enabled: true },
  { id: 'rr_0002', name: 'Complaint raised', condition: 'complaint', destination: { type: 'team', value: 'Client care' }, schedule: 'always', priority: 2, enabled: true },
  { id: 'rr_0003', name: 'Refund requested', condition: 'refund_requested', destination: { type: 'employee', value: 'Sam Rivera' }, schedule: 'open_hours', priority: 3, enabled: true },
  { id: 'rr_0004', name: 'Large transaction needs approval', condition: 'transaction_over_threshold', conditionDetail: 'Over $2,000', destination: { type: 'employee', value: 'Avery Chen' }, schedule: 'open_hours', priority: 4, enabled: true },
  { id: 'rr_0005', name: 'After-hours calls', condition: 'cannot_answer', destination: { type: 'phone_number', value: '+1 555 0188' }, schedule: 'after_hours', priority: 5, enabled: true },
  { id: 'rr_0006', name: 'Weekend enquiries', condition: 'cannot_answer', destination: { type: 'queue', value: 'Weekend callback queue' }, schedule: 'weekends', priority: 6, enabled: true },
  { id: 'rr_0007', name: 'Priority client keywords', condition: 'keyword_match', conditionDetail: 'urgent, deadline, board meeting', destination: { type: 'department', value: 'Advisory' }, schedule: 'always', priority: 7, enabled: false },
  { id: 'rr_0008', name: 'Scheduling system unavailable', condition: 'integration_unavailable', destination: { type: 'external_system', value: 'Overflow answering service' }, schedule: 'holidays', priority: 8, enabled: false },
]

export const routingRuleSeed: RoutingRule[] = ROUTING_RULES.map((rule) => ({
  ...rule,
  organizationId: MOCK_ORGANIZATION_ID,
}))
