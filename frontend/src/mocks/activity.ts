import type { ActivityEvent, Escalation } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const MINUTE = 60_000

function isoAgo(minutesAgo: number): string {
  return new Date(NOW - minutesAgo * MINUTE).toISOString()
}

/**
 * US-2.4: time, activity type, customer/context, channel, status per item.
 *
 * The base array is annotated because `.map()` below blocks contextual typing —
 * without it, `status: 'success'` widens to `string` and fails `tsc`.
 */
const ACTIVITY_EVENTS: Omit<ActivityEvent, 'organizationId'>[] = [
  { id: 'act_0001', at: isoAgo(4), title: 'Appointment booked', customerRef: 'Alex Morgan', channel: 'voice', system: 'Scheduling', status: 'success', conversationId: 'conv_0001' },
  { id: 'act_0002', at: isoAgo(11), title: 'Payment link sent', customerRef: 'Dana Wu', channel: 'sms', system: 'Payments', status: 'success', conversationId: 'conv_0002' },
  { id: 'act_0003', at: isoAgo(19), title: 'Escalated to team', customerRef: 'Ibrahim Khan', channel: 'voice', system: 'Escalation & Routing', status: 'escalated', conversationId: 'conv_0003' },
  { id: 'act_0004', at: isoAgo(27), title: 'Customer record updated', customerRef: 'Rosa Delgado', channel: 'web', system: 'Customer Records', status: 'success', conversationId: 'conv_0004' },
  { id: 'act_0005', at: isoAgo(38), title: 'Appointment rescheduled', customerRef: 'Nate Fischer', channel: 'sms', system: 'Scheduling', status: 'success', conversationId: 'conv_0005' },
  { id: 'act_0006', at: isoAgo(52), title: 'Scheduling lookup failed', customerRef: 'Yuki Tanaka', channel: 'voice', system: 'Scheduling', status: 'error', conversationId: 'conv_0006' },
  { id: 'act_0007', at: isoAgo(66), title: 'Callback requested', customerRef: 'Marcus Bell', channel: 'voice', system: 'Customer Records', status: 'pending', conversationId: 'conv_0007' },
  { id: 'act_0008', at: isoAgo(81), title: 'Business hours answered', customerRef: 'Alex Morgan', channel: 'sms', system: 'Knowledge', status: 'info', conversationId: 'conv_0008' },
  { id: 'act_0009', at: isoAgo(97), title: 'Invoice status shared', customerRef: 'Dana Wu', channel: 'voice', system: 'Billing', status: 'success', conversationId: 'conv_0009' },
  { id: 'act_0010', at: isoAgo(118), title: 'Escalated to team', customerRef: 'Ibrahim Khan', channel: 'web', system: 'Escalation & Routing', status: 'escalated', conversationId: 'conv_0010' },
  { id: 'act_0011', at: isoAgo(140), title: 'Appointment cancelled', customerRef: 'Rosa Delgado', channel: 'sms', system: 'Scheduling', status: 'success', conversationId: 'conv_0011' },
  { id: 'act_0012', at: isoAgo(166), title: 'Pricing question answered', customerRef: 'Nate Fischer', channel: 'voice', system: 'Knowledge', status: 'info', conversationId: 'conv_0012' },
]

export const activityEventSeed: ActivityEvent[] = ACTIVITY_EVENTS.map((event) => ({
  ...event,
  organizationId: MOCK_ORGANIZATION_ID,
}))

/** US-2.5: all four statuses appear so the Overview table cannot hide a branch. */
const ESCALATIONS: Omit<Escalation, 'organizationId'>[] = [
  { id: 'esc_0001', conversationId: 'conv_0003', customerName: 'Ibrahim Khan', reason: 'Customer asked to speak to a person', assignedTo: undefined, status: 'new', createdAt: isoAgo(19) },
  { id: 'esc_0002', conversationId: 'conv_0010', customerName: 'Rosa Delgado', reason: 'Refund requested', assignedTo: 'Sam Rivera', status: 'assigned', createdAt: isoAgo(118) },
  { id: 'esc_0003', conversationId: 'conv_0018', customerName: 'Marcus Bell', reason: 'Complaint about a missed appointment', assignedTo: 'Taylor Brooks', status: 'in_progress', createdAt: isoAgo(240) },
  { id: 'esc_0004', conversationId: 'conv_0023', customerName: 'Yuki Tanaka', reason: 'Concierge could not answer the question', assignedTo: 'Priya Shah', status: 'resolved', createdAt: isoAgo(420) },
  { id: 'esc_0005', conversationId: 'conv_0031', customerName: 'Dana Wu', reason: 'Transaction over approval threshold', assignedTo: 'Avery Chen', status: 'in_progress', createdAt: isoAgo(610) },
  { id: 'esc_0006', conversationId: 'conv_0038', customerName: 'Alex Morgan', reason: 'Scheduling system unavailable', assignedTo: undefined, status: 'new', createdAt: isoAgo(880) },
]

export const escalationSeed: Escalation[] = ESCALATIONS.map((escalation) => ({
  ...escalation,
  organizationId: MOCK_ORGANIZATION_ID,
}))
