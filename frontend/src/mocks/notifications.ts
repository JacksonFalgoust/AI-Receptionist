import type { Notification } from '@/types'

const NOW = Date.now()
const MINUTE = 60_000

function isoAgo(minutesAgo: number): string {
  return new Date(NOW - minutesAgo * MINUTE).toISOString()
}

/**
 * PRD §6.2: the notification centre surfaces failed integrations, escalations,
 * workflow errors, configuration issues, usage limits, and security events —
 * all six `NotificationKind` values, each with at least one example.
 */
export const notificationSeed: Notification[] = [
  {
    id: 'ntf_0001',
    kind: 'integration_failure',
    title: 'Scheduling connection needs attention',
    body: 'Concierge could not reach the scheduling system on the last three attempts.',
    at: isoAgo(9),
    read: false,
    href: '/integrations',
  },
  {
    id: 'ntf_0002',
    kind: 'escalation',
    title: 'New escalation waiting',
    body: 'Ibrahim Khan asked to speak to a person and has not been assigned.',
    at: isoAgo(19),
    read: false,
    href: '/routing',
  },
  {
    id: 'ntf_0003',
    kind: 'workflow_error',
    title: 'Appointment booking workflow stopped',
    body: 'A step failed while confirming availability. The customer was offered a callback.',
    at: isoAgo(74),
    read: false,
    href: '/concierge/workflows',
  },
  {
    id: 'ntf_0004',
    kind: 'configuration_issue',
    title: 'Business hours are incomplete',
    body: 'Saturday has no opening hours set, so Concierge treats it as closed.',
    at: isoAgo(320),
    read: true,
    href: '/concierge/configuration',
  },
  {
    id: 'ntf_0005',
    kind: 'usage_limit',
    title: 'Voice minutes at 80% of plan',
    body: 'You have used 9,600 of 12,000 included voice minutes this period.',
    at: isoAgo(700),
    read: true,
    href: '/admin/billing',
  },
  {
    id: 'ntf_0006',
    kind: 'security_event',
    title: 'New sign-in from an unrecognised device',
    body: 'Avery Chen signed in from a device that has not been used before.',
    at: isoAgo(1500),
    read: true,
    href: '/admin/users',
  },
]
