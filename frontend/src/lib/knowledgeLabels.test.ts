import { describe, expect, it } from 'vitest'

import { KNOWLEDGE_TYPE_LABELS, KNOWLEDGE_TYPES, knowledgeTypeLabel } from './knowledgeLabels'

describe('knowledgeLabels', () => {
  it('covers all ten knowledge sources in PRD §16.1', () => {
    // `Record<KnowledgeType, string>` makes a missing label a compile error;
    // this guards the ordered array staying in step with the record, since
    // the filter's option list is built from the array and would silently
    // drop a type otherwise.
    expect(KNOWLEDGE_TYPES).toHaveLength(10)
    expect([...KNOWLEDGE_TYPES].sort()).toEqual(Object.keys(KNOWLEDGE_TYPE_LABELS).sort())
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
