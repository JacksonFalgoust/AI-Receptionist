import type { IntegrationCategory } from '@/types'

/**
 * PRD §17.1's ten integration categories, named as the business names them.
 * `IntegrationStatus` already has labels in `statusTone`; only the category
 * side needs this.
 */
export const INTEGRATION_CATEGORY_LABELS: Record<IntegrationCategory, string> = {
  crm: 'CRM',
  reservations: 'Reservations',
  scheduling: 'Scheduling',
  payments: 'Payments',
  inventory: 'Inventory',
  erp: 'ERP',
  service_management: 'Service Management',
  customer_data: 'Customer Data',
  communications: 'Communications',
  custom: 'Custom Integrations',
}

/**
 * Derived from the label record rather than listed a second time: a hand-kept
 * array compiles cleanly while silently omitting a newly added category from
 * the filter. `Object.keys` preserves the record's declaration order, so the
 * record above is also the filter order.
 */
export const INTEGRATION_CATEGORIES = Object.keys(
  INTEGRATION_CATEGORY_LABELS,
) as IntegrationCategory[]

export function integrationCategoryLabel(category: IntegrationCategory): string {
  return INTEGRATION_CATEGORY_LABELS[category]
}
