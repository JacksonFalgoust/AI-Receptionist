import { describe, expect, it } from 'vitest'

import { statusTone } from './statusTone'
import {
  KNOWLEDGE_STATUSES,
  KNOWLEDGE_TYPE_LABELS,
  KNOWLEDGE_TYPES,
  knowledgeTypeLabel,
} from './knowledgeLabels'

describe('knowledgeLabels', () => {
  // Drift is caught at compile time — both arrays are derived from a
  // `Record` keyed by the union, so growing `KnowledgeType` or
  // `KnowledgeStatus` fails the build until the new member is named. These
  // guard the other direction: that nobody quietly shrinks the set the
  // filters offer, which would leave rows in the table unreachable by filter.
  it('covers all ten knowledge sources in PRD §16.1', () => {
    expect(KNOWLEDGE_TYPES).toHaveLength(10)
    expect(KNOWLEDGE_TYPES).toContain('faq')
    expect(KNOWLEDGE_TYPES).toContain('url')
  })

  it('covers all five statuses in US-5.1, in the order the story lists them', () => {
    expect(KNOWLEDGE_STATUSES.map((status) => statusTone(status).label)).toEqual([
      'Active',
      'Processing',
      'Needs review',
      'Error',
      'Disabled',
    ])
  })

  it('names each type the way the business does, not the way the storage does', () => {
    expect(knowledgeTypeLabel('faq')).toBe('FAQ')
    expect(knowledgeTypeLabel('document')).toBe('Uploaded document')
    expect(knowledgeTypeLabel('url')).toBe('Website content')
    expect(knowledgeTypeLabel('instruction')).toBe('Business instruction')
    expect(knowledgeTypeLabel('product')).toBe('Product information')
  })

  it('never leaks an underscored domain value into the interface', () => {
    // PRD §3.1: business language in UI copy.
    for (const label of Object.values(KNOWLEDGE_TYPE_LABELS)) {
      expect(label).not.toMatch(/_/)
    }
  })
})
