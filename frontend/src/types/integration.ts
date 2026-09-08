import type { Id, IsoDateTime, TenantScoped } from './common'

/** PRD §17.1 */
export type IntegrationCategory =
  | 'crm'
  | 'reservations'
  | 'scheduling'
  | 'payments'
  | 'inventory'
  | 'erp'
  | 'service_management'
  | 'customer_data'
  | 'communications'
  | 'custom'

/** PRD §17.2 */
export type IntegrationStatus =
  | 'connected'
  | 'not_connected'
  | 'setup_required'
  | 'connection_error'
  | 'authentication_expired'

export interface Integration extends TenantScoped {
  id: Id
  name: string
  category: IntegrationCategory
  status: IntegrationStatus
  lastActivityAt?: IsoDateTime
  /**
   * Display label for the linked account (e.g. "ops@horizonpartners.com").
   * PRD §17.3 / §47: credentials are never returned once stored.
   */
  connectedAccount?: string
  /** Names of the Features that depend on this connection. */
  features: string[]
}
