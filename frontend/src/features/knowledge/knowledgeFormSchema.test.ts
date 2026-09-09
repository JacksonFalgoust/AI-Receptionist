import { describe, expect, it } from 'vitest'

import type { KnowledgeItem } from '@/types'

import {
  emptyKnowledgeFormValues,
  itemToFormValues,
  knowledgeFormSchema,
  knowledgeFormValuesToOutput,
  resolveKnowledgeStatus,
} from './knowledgeFormSchema'

const baseValues = {
  title: 'Refund policy',
  type: 'policy' as const,
  category: 'Policies',
  content: 'Refunds are reviewed within five business days.',
  tagsText: 'policy, refunds',
  active: true,
  effectiveDate: '',
  expirationDate: '',
  websiteUrl: '',
  documentFileName: '',
}

const baseItem: KnowledgeItem = {
  id: 'kn_0007',
  organizationId: 'org_horizon',
  title: 'Refund policy',
  type: 'policy',
  status: 'active',
  source: 'Manual entry',
  category: 'Policies',
  content: 'Refunds are reviewed within five business days.',
  tags: ['policy', 'refunds'],
  updatedAt: '2026-09-03T14:12:00.000Z',
}

describe('knowledgeFormSchema', () => {
  const schema = knowledgeFormSchema({ hasExistingSource: false })

  it('requires a title', () => {
    const result = schema.safeParse({ ...baseValues, title: '' })
    expect(result.success).toBe(false)
  })

  it('requires a type', () => {
    const result = schema.safeParse({ ...baseValues, type: '' })
    expect(result.success).toBe(false)
  })

  it('requires content for a manually-authored type', () => {
    const result = schema.safeParse({ ...baseValues, type: 'faq', content: '' })
    expect(result.success).toBe(false)
  })

  it('does not require content for a URL — the page supplies it', () => {
    const result = schema.safeParse({
      ...baseValues,
      type: 'url',
      content: '',
      websiteUrl: 'https://horizonpartners.example.com/services',
    })
    expect(result.success).toBe(true)
  })

  it('does not require content for a document — the file supplies it', () => {
    const result = knowledgeFormSchema({ hasExistingSource: true }).safeParse({
      ...baseValues,
      type: 'document',
      content: '',
    })
    expect(result.success).toBe(true)
  })

  it('requires a website address when the type is url', () => {
    const result = schema.safeParse({ ...baseValues, type: 'url', websiteUrl: '' })
    expect(result.success).toBe(false)
  })

  it('rejects a website address that is not a valid URL', () => {
    const result = schema.safeParse({ ...baseValues, type: 'url', websiteUrl: 'not a url' })
    expect(result.success).toBe(false)
  })

  it('requires a file when creating a document with no existing source', () => {
    const result = knowledgeFormSchema({ hasExistingSource: false }).safeParse({
      ...baseValues,
      type: 'document',
      documentFileName: '',
    })
    expect(result.success).toBe(false)
  })

  it('does not require a new file when editing a document that already has one', () => {
    const result = knowledgeFormSchema({ hasExistingSource: true }).safeParse({
      ...baseValues,
      type: 'document',
      documentFileName: '',
    })
    expect(result.success).toBe(true)
  })

  it('rejects an expiration date on or before the effective date', () => {
    const result = schema.safeParse({
      ...baseValues,
      effectiveDate: '2026-06-01',
      expirationDate: '2026-06-01',
    })
    expect(result.success).toBe(false)
  })

  it('accepts an expiration date after the effective date', () => {
    const result = schema.safeParse({
      ...baseValues,
      effectiveDate: '2026-06-01',
      expirationDate: '2026-12-01',
    })
    expect(result.success).toBe(true)
  })

  it('accepts a fully valid manually-authored item', () => {
    expect(schema.safeParse(baseValues).success).toBe(true)
  })
})

describe('resolveKnowledgeStatus', () => {
  it('sets Active when the toggle is on', () => {
    expect(
      resolveKnowledgeStatus({ active: true, type: 'faq', isNewDocumentUpload: false }),
    ).toBe('active')
  })

  it('sets Processing for a newly uploaded document, even with the toggle on', () => {
    // Nothing is editable until the upload has been read — the toggle cannot
    // force it straight to Active.
    expect(
      resolveKnowledgeStatus({ active: true, type: 'document', isNewDocumentUpload: true }),
    ).toBe('processing')
  })

  it('preserves a status the system set when the toggle is off', () => {
    expect(
      resolveKnowledgeStatus({
        active: false,
        type: 'policy',
        isNewDocumentUpload: false,
        previousStatus: 'needs_review',
      }),
    ).toBe('needs_review')
  })

  it('preserves Error the same way', () => {
    expect(
      resolveKnowledgeStatus({
        active: false,
        type: 'document',
        isNewDocumentUpload: false,
        previousStatus: 'error',
      }),
    ).toBe('error')
  })

  it('falls back to Disabled when the toggle is off and nothing to preserve', () => {
    expect(
      resolveKnowledgeStatus({
        active: false,
        type: 'faq',
        isNewDocumentUpload: false,
        previousStatus: 'active',
      }),
    ).toBe('disabled')
  })

  it('falls back to Disabled on a new item with the toggle off', () => {
    expect(
      resolveKnowledgeStatus({ active: false, type: 'faq', isNewDocumentUpload: false }),
    ).toBe('disabled')
  })
})

describe('itemToFormValues', () => {
  it('carries the plain fields across unchanged', () => {
    const values = itemToFormValues(baseItem)
    expect(values.title).toBe('Refund policy')
    expect(values.type).toBe('policy')
    expect(values.category).toBe('Policies')
    expect(values.content).toBe('Refunds are reviewed within five business days.')
  })

  it('joins tags for display in a single text field', () => {
    expect(itemToFormValues(baseItem).tagsText).toBe('policy, refunds')
  })

  it('reads the toggle on for an Active item', () => {
    expect(itemToFormValues(baseItem).active).toBe(true)
  })

  it('reads the toggle off for a status the system set', () => {
    expect(itemToFormValues({ ...baseItem, status: 'needs_review' }).active).toBe(false)
  })

  it('never pre-fills a file — a file input cannot be set from a filename', () => {
    expect(itemToFormValues({ ...baseItem, type: 'document', source: 'handbook.pdf' }).documentFileName).toBe('')
  })

  it('carries the source into the website field only for a url item', () => {
    expect(
      itemToFormValues({ ...baseItem, type: 'url', source: 'https://example.com' }).websiteUrl,
    ).toBe('https://example.com')
    expect(itemToFormValues(baseItem).websiteUrl).toBe('')
  })

  it('formats an ISO date for a native date input', () => {
    const values = itemToFormValues({ ...baseItem, effectiveDate: '2026-01-15T00:00:00.000Z' })
    expect(values.effectiveDate).toBe('2026-01-15')
  })

  it('leaves a date blank when the item has none', () => {
    expect(itemToFormValues(baseItem).expirationDate).toBe('')
  })
})

describe('knowledgeFormValuesToOutput', () => {
  it('parses the comma-separated tags text into a trimmed array', () => {
    const output = knowledgeFormValuesToOutput({ ...baseValues, tagsText: ' policy ,  refunds ,,billing ' })
    expect(output.tags).toEqual(['policy', 'refunds', 'billing'])
  })

  it('sends the website address as the source for a url item', () => {
    const output = knowledgeFormValuesToOutput({
      ...baseValues,
      type: 'url',
      websiteUrl: 'https://example.com/services',
    })
    expect(output.source).toBe('https://example.com/services')
  })

  it('sends the chosen filename as the source for a new document upload', () => {
    const output = knowledgeFormValuesToOutput({
      ...baseValues,
      type: 'document',
      documentFileName: 'handbook.pdf',
    })
    expect(output.source).toBe('handbook.pdf')
  })

  it('preserves the existing source when a document is edited without a new file', () => {
    const output = knowledgeFormValuesToOutput(
      { ...baseValues, type: 'document', documentFileName: '' },
      { ...baseItem, type: 'document', source: 'handbook.pdf' },
    )
    expect(output.source).toBe('handbook.pdf')
  })

  it('leaves source unset for a manually-authored type', () => {
    const output = knowledgeFormValuesToOutput({ ...baseValues, type: 'faq' })
    expect(output.source).toBeUndefined()
  })

  it('sets Processing on a fresh document upload regardless of the toggle', () => {
    const output = knowledgeFormValuesToOutput({
      ...baseValues,
      type: 'document',
      documentFileName: 'handbook.pdf',
      active: true,
    })
    expect(output.status).toBe('processing')
  })

  it('preserves the original status through an edit when the toggle is off', () => {
    const output = knowledgeFormValuesToOutput(
      { ...baseValues, active: false },
      { ...baseItem, status: 'needs_review' },
    )
    expect(output.status).toBe('needs_review')
  })

  it('converts a blank date to undefined, not an empty string', () => {
    const output = knowledgeFormValuesToOutput(baseValues)
    expect(output.effectiveDate).toBeUndefined()
    expect(output.expirationDate).toBeUndefined()
  })

  it('converts a date-input value to an ISO timestamp', () => {
    const output = knowledgeFormValuesToOutput({ ...baseValues, effectiveDate: '2026-06-01' })
    expect(output.effectiveDate).toBe('2026-06-01T00:00:00.000Z')
  })

  it('trims category and content, omitting them when blank', () => {
    const output = knowledgeFormValuesToOutput({ ...baseValues, category: '  ', content: '  ' })
    expect(output.category).toBeUndefined()
    expect(output.content).toBeUndefined()
  })
})

describe('emptyKnowledgeFormValues', () => {
  it('seeds the type from the add menu, leaving everything else blank', () => {
    const values = emptyKnowledgeFormValues('faq')
    expect(values.type).toBe('faq')
    expect(values.title).toBe('')
    expect(values.tagsText).toBe('')
  })

  it('leaves the type open when nothing was seeded, so every type stays reachable', () => {
    expect(emptyKnowledgeFormValues().type).toBe('')
  })

  it('defaults a new item to Active', () => {
    expect(emptyKnowledgeFormValues().active).toBe(true)
  })
})
