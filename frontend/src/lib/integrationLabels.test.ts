import { describe, expect, it } from 'vitest'

import {
  INTEGRATION_CATEGORIES,
  INTEGRATION_CATEGORY_LABELS,
  integrationCategoryLabel,
} from './integrationLabels'

describe('integrationLabels', () => {
  // Drift is caught at compile time — INTEGRATION_CATEGORIES is derived from a
  // Record keyed by the union, so growing IntegrationCategory fails the build
  // until the new member is named. This guards the other direction: that
  // nobody quietly shrinks the set the filter offers.
  it('covers all ten categories in PRD §17.1', () => {
    expect(INTEGRATION_CATEGORIES).toHaveLength(10)
    expect(INTEGRATION_CATEGORIES).toContain('crm')
    expect(INTEGRATION_CATEGORIES).toContain('custom')
  })

  it('names each category the way the business does, not the way the storage does', () => {
    expect(integrationCategoryLabel('crm')).toBe('CRM')
    expect(integrationCategoryLabel('erp')).toBe('ERP')
    expect(integrationCategoryLabel('service_management')).toBe('Service Management')
    expect(integrationCategoryLabel('customer_data')).toBe('Customer Data')
    expect(integrationCategoryLabel('custom')).toBe('Custom Integrations')
  })

  it('never leaks an underscored domain value into the interface', () => {
    // PRD §3.1: business language in UI copy.
    for (const label of Object.values(INTEGRATION_CATEGORY_LABELS)) {
      expect(label).not.toMatch(/_/)
    }
  })
})
