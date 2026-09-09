import type { KnowledgeType } from '@/types'

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

/** Filter order: the types an administrator reaches for first. */
export const KNOWLEDGE_TYPES: KnowledgeType[] = [
  'faq',
  'policy',
  'procedure',
  'product',
  'service',
  'pricing',
  'location',
  'instruction',
  'document',
  'url',
]

export function knowledgeTypeLabel(type: KnowledgeType): string {
  return KNOWLEDGE_TYPE_LABELS[type]
}
