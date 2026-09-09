import type {
  BusinessHours,
  ConciergeConfiguration,
  ConciergeStatus,
  Feature,
} from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const HOUR = 60 * 60 * 1000

/** US-2.3: Voice and SMS only on the status card — no Web. */
export const conciergeStatusSeed: ConciergeStatus = {
  state: 'active',
  channels: [
    { channel: 'voice', enabled: true, health: 'ok' },
    { channel: 'sms', enabled: true, health: 'degraded' },
  ],
  connectedSystems: [
    { id: 'int_scheduling', name: 'Scheduling', health: 'down', lastSyncAt: new Date(NOW - 3 * HOUR).toISOString() },
    { id: 'int_customer_records', name: 'Customer Records', health: 'ok', lastSyncAt: new Date(NOW - 0.2 * HOUR).toISOString() },
    { id: 'int_payments', name: 'Payments', health: 'ok', lastSyncAt: new Date(NOW - 0.5 * HOUR).toISOString() },
  ],
  lastConfigurationChangeAt: new Date(NOW - 26 * HOUR).toISOString(),
}

const BUSINESS_HOURS: BusinessHours[] = [
  { day: 0, closed: true },
  { day: 1, open: '08:30', close: '17:30', closed: false },
  { day: 2, open: '08:30', close: '17:30', closed: false },
  { day: 3, open: '08:30', close: '17:30', closed: false },
  { day: 4, open: '08:30', close: '17:30', closed: false },
  { day: 5, open: '08:30', close: '16:00', closed: false },
  { day: 6, closed: true },
]

export const conciergeConfigurationSeed: ConciergeConfiguration = {
  organizationId: MOCK_ORGANIZATION_ID,
  businessProfile: {
    name: 'Horizon Partners',
    description:
      'A professional services firm helping clients plan, schedule, and manage ongoing engagements.',
    phone: '+1 555 0100',
    website: 'https://horizonpartners.example.com',
    timezone: 'America/Chicago',
    address: '1200 Meridian Way, Suite 400',
    locations: '3 locations',
    hours: BUSINESS_HOURS,
  },
  identity: {
    name: 'Horizon Concierge',
    greeting: 'Thanks for contacting Horizon Partners. How can I help today?',
    closing: 'Thanks for your time. We look forward to speaking again.',
    voice: 'Warm — Female',
    tone: 'professional',
    primaryLanguage: 'en-US',
    supportedLanguages: ['en-US', 'es-US'],
  },
  terminology: {
    customer: 'Client',
    reservation: 'Appointment',
    location: 'Office',
    employee: 'Team member',
  },
  // PRD §13.4: a draft must never reach production on save alone. Seeded clean
  // so a test can prove `saveDraft` sets this and only `publish` clears it.
  hasUnpublishedChanges: false,
  lastPublishedAt: new Date(NOW - 26 * HOUR).toISOString(),
}

/** PRD §14.2 — all five `FeatureStatus` values are represented. */
export const featureSeed: Feature[] = [
  { id: 'feat_answer_calls', name: 'Answer Calls', description: 'Concierge answers inbound calls and handles common requests.', status: 'enabled', highImpact: true },
  { id: 'feat_sms', name: 'SMS', description: 'Concierge replies to text messages and sends confirmations.', status: 'enabled', highImpact: false },
  { id: 'feat_scheduling', name: 'Scheduling', description: 'Book, reschedule, and cancel appointments.', status: 'error', requiredIntegrationId: 'int_scheduling', requiredIntegrationName: 'Scheduling', highImpact: false },
  { id: 'feat_customer_lookup', name: 'Customer Lookup', description: 'Find an existing client record during a conversation.', status: 'enabled', requiredIntegrationId: 'int_customer_records', requiredIntegrationName: 'Customer Records', highImpact: false },
  { id: 'feat_payments', name: 'Payments', description: 'Send a payment link and confirm when it is paid.', status: 'enabled', requiredIntegrationId: 'int_payments', requiredIntegrationName: 'Payments', highImpact: true },
  { id: 'feat_order_status', name: 'Order Status', description: 'Answer questions about the status of an existing request.', status: 'connection_required', requiredIntegrationId: 'int_erp', requiredIntegrationName: 'Operations Platform', highImpact: false },
  { id: 'feat_inventory', name: 'Inventory Lookup', description: 'Check availability of services and resources.', status: 'setup_required', requiredIntegrationId: 'int_inventory', requiredIntegrationName: 'Inventory', highImpact: false },
  { id: 'feat_escalation', name: 'Human Escalation', description: 'Hand a conversation to a team member when a person is needed.', status: 'enabled', highImpact: true },
  { id: 'feat_surveys', name: 'Follow-up Surveys', description: 'Send a short survey after a completed request.', status: 'disabled', highImpact: false },
]
