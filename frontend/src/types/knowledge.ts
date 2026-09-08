import type { Id, IsoDateTime, TenantScoped } from './common'

/** PRD §16.1 */
export type KnowledgeType =
  | 'faq'
  | 'policy'
  | 'procedure'
  | 'product'
  | 'service'
  | 'pricing'
  | 'location'
  | 'instruction'
  | 'document'
  | 'url'

/** PRD §16.2 */
export type KnowledgeStatus =
  | 'active'
  | 'processing'
  | 'needs_review'
  | 'error'
  | 'disabled'

export interface KnowledgeItem extends TenantScoped {
  id: Id
  title: string
  type: KnowledgeType
  status: KnowledgeStatus
  /** Where it came from — an uploaded filename, a URL, or "Manual entry". */
  source: string
  category?: string
  content?: string
  tags: string[]
  effectiveDate?: IsoDateTime
  expirationDate?: IsoDateTime
  updatedAt: IsoDateTime
}
