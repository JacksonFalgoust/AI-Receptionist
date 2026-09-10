import type { IntegrationCategory } from '@/types'

export interface AuthField {
  name: string
  label: string
  /** `secret` renders as a password input and is never prefilled (PRD §17.3, §47). */
  type: 'text' | 'secret'
  required: boolean
}

/**
 * Every connection needs a human-readable name for the linked account, and
 * `ConnectIntegrationInput` takes it as a first-class argument rather than as
 * a credential — so it lives outside the per-category map.
 */
export const ACCOUNT_LABEL_FIELD: AuthField = {
  name: 'accountLabel',
  label: 'Account name',
  type: 'text',
  required: true,
}

/**
 * What each category asks for before it can connect. Exhaustive over
 * `IntegrationCategory`, so a new category is a compile error here until it is
 * given fields — the same guarantee `INTEGRATION_CATEGORY_LABELS` gives labels.
 *
 * This is the single file E6 replaces when a real credential contract exists.
 * Nothing here is sent anywhere today: the mock service discards `credentials`.
 */
export const INTEGRATION_AUTH_FIELDS: Record<IntegrationCategory, AuthField[]> = {
  crm: [
    { name: 'instanceUrl', label: 'Instance address', type: 'text', required: true },
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
  ],
  reservations: [
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
    { name: 'locationId', label: 'Location ID', type: 'text', required: false },
  ],
  scheduling: [
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
    { name: 'calendarId', label: 'Calendar ID', type: 'text', required: false },
  ],
  payments: [
    { name: 'publishableKey', label: 'Publishable key', type: 'text', required: true },
    { name: 'secretKey', label: 'Secret key', type: 'secret', required: true },
  ],
  inventory: [
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
    { name: 'warehouseId', label: 'Warehouse ID', type: 'text', required: false },
  ],
  erp: [
    { name: 'companyId', label: 'Company ID', type: 'text', required: true },
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
  ],
  service_management: [
    { name: 'workspace', label: 'Workspace', type: 'text', required: true },
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
  ],
  customer_data: [
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
    { name: 'region', label: 'Data region', type: 'text', required: false },
  ],
  communications: [
    { name: 'accountSid', label: 'Account SID', type: 'text', required: true },
    { name: 'authToken', label: 'Auth token', type: 'secret', required: true },
  ],
  custom: [
    { name: 'endpoint', label: 'Endpoint address', type: 'text', required: true },
    { name: 'apiKey', label: 'API key', type: 'secret', required: true },
  ],
}

export function integrationAuthFields(category: IntegrationCategory): AuthField[] {
  return INTEGRATION_AUTH_FIELDS[category]
}
