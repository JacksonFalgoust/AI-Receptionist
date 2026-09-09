import type { KnowledgeStatus, KnowledgeType } from '@/types'

/**
 * PRD §16.1's ten knowledge sources, named as the business names them.
 * `KnowledgeStatus` already has labels in `statusTone`; only the type side
 * needs this.
 */
export const KNOWLEDGE_TYPE_LABELS: Record<KnowledgeType, string> = {
  faq: 'FAQ',
  policy: 'Policy',
  procedure: 'Procedure',
  product: 'Product information',
  service: 'Service description',
  pricing: 'Pricing information',
  location: 'Location information',
  instruction: 'Business instruction',
  document: 'Uploaded document',
  url: 'Website content',
}

/**
 * Derived from the label record rather than listed a second time: a hand-kept
 * array compiles cleanly while silently omitting a newly added type from the
 * filter, which would also make `?type=<new>` in a shared URL fall back to
 * unfiltered with no chip to explain it. `Object.keys` preserves the record's
 * declaration order, so the record above is also the filter order.
 */
export const KNOWLEDGE_TYPES = Object.keys(KNOWLEDGE_TYPE_LABELS) as KnowledgeType[]

/**
 * The statuses in US-5.1, in the order the story lists them. Labels come from
 * `statusTone`; this record exists to make the set exhaustive at compile time
 * for exactly the reason above — `Record<KnowledgeStatus, true>` fails to
 * build the moment the union grows.
 */
const KNOWLEDGE_STATUS_PRESENCE: Record<KnowledgeStatus, true> = {
  active: true,
  processing: true,
  needs_review: true,
  error: true,
  disabled: true,
}

export const KNOWLEDGE_STATUSES = Object.keys(KNOWLEDGE_STATUS_PRESENCE) as KnowledgeStatus[]

export function knowledgeTypeLabel(type: KnowledgeType): string {
  return KNOWLEDGE_TYPE_LABELS[type]
}
