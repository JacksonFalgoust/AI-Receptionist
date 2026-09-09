import type { Integration } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const HOUR = 60 * 60 * 1000

function isoHoursAgo(hours: number): string {
  return new Date(NOW - hours * HOUR).toISOString()
}

/**
 * All five `IntegrationStatus` values appear. `connectedAccount` is a display
 * label only — PRD §17.3 and §47: a credential is never returned once stored,
 * so nothing here resembles one.
 *
 * The base array is annotated so `.map()` does not widen `status` to `string`.
 */
const INTEGRATIONS: Omit<Integration, 'organizationId'>[] = [
  { id: 'int_customer_records', name: 'Customer Records', category: 'crm', status: 'connected', lastActivityAt: isoHoursAgo(0.2), connectedAccount: 'ops@horizonpartners.example.com', features: ['Customer Lookup', 'Human Escalation'] },
  { id: 'int_scheduling', name: 'Scheduling', category: 'scheduling', status: 'connection_error', lastActivityAt: isoHoursAgo(3), connectedAccount: 'scheduling@horizonpartners.example.com', features: ['Scheduling'] },
  { id: 'int_payments', name: 'Payments', category: 'payments', status: 'connected', lastActivityAt: isoHoursAgo(0.5), connectedAccount: 'billing@horizonpartners.example.com', features: ['Payments'] },
  { id: 'int_messaging', name: 'Messaging', category: 'communications', status: 'connected', lastActivityAt: isoHoursAgo(0.1), connectedAccount: '+1 555 0100', features: ['SMS', 'Answer Calls'] },
  { id: 'int_customer_data', name: 'Customer Data Platform', category: 'customer_data', status: 'authentication_expired', lastActivityAt: isoHoursAgo(72), connectedAccount: 'data@horizonpartners.example.com', features: ['Customer Lookup'] },
  { id: 'int_erp', name: 'Operations Platform', category: 'erp', status: 'setup_required', features: ['Order Status'] },
  { id: 'int_inventory', name: 'Inventory', category: 'inventory', status: 'setup_required', features: ['Inventory Lookup'] },
  { id: 'int_reservations', name: 'Reservations', category: 'reservations', status: 'not_connected', features: [] },
  { id: 'int_service_desk', name: 'Service Desk', category: 'service_management', status: 'not_connected', features: [] },
  { id: 'int_internal_tools', name: 'Internal Tools', category: 'custom', status: 'not_connected', features: [] },
]

export const integrationSeed: Integration[] = INTEGRATIONS.map((integration) => ({
  ...integration,
  organizationId: MOCK_ORGANIZATION_ID,
}))
