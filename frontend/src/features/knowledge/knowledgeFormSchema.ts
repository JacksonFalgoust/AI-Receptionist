import { z } from 'zod'

import type { KnowledgeItem, KnowledgeStatus, KnowledgeType } from '@/types'

/**
 * Bound directly to the form's controls. `type` is `''` until chosen — the
 * "Add business information" action deliberately seeds no type, and an empty
 * select value must be representable — and `documentFileName` stands in for a
 * real file: E6 wires up the actual upload, so all the mock has to reason
 * about is the name the reader will see in the Source column.
 */
export interface KnowledgeFormValues {
  title: string
  type: KnowledgeType | ''
  category: string
  content: string
  tagsText: string
  active: boolean
  effectiveDate: string
  expirationDate: string
  websiteUrl: string
  documentFileName: string
}

const TYPES_WITH_EXTERNAL_CONTENT: (KnowledgeType | '')[] = ['document', 'url']

/**
 * `hasExistingSource` is true only when editing an item that already has a
 * source on file — it is what lets a document edit skip re-uploading, and is
 * always false for a new item.
 */
export function knowledgeFormSchema(options: { hasExistingSource: boolean }) {
  return z
    .object({
      title: z.string().trim().min(1, 'Enter a title'),
      // A plain z.string() infers as `string`, not `KnowledgeType | ''`, and
      // that mismatch is what the object's inferred type has to match for
      // `useForm<KnowledgeFormValues>`'s resolver to type-check. The runtime
      // check stays a formality — the select can only ever produce one of
      // these values or ''.
      type: z.custom<KnowledgeType | ''>((value) => typeof value === 'string'),
      category: z.string(),
      content: z.string(),
      tagsText: z.string(),
      active: z.boolean(),
      effectiveDate: z.string(),
      expirationDate: z.string(),
      websiteUrl: z.string(),
      documentFileName: z.string(),
    })
    .superRefine((values, ctx) => {
      if (values.type === '') {
        ctx.addIssue({ code: 'custom', path: ['type'], message: 'Select a type' })
        return
      }

      if (
        values.content.trim() === '' &&
        !TYPES_WITH_EXTERNAL_CONTENT.includes(values.type)
      ) {
        ctx.addIssue({
          code: 'custom',
          path: ['content'],
          message: 'Enter the content Concierge should use',
        })
      }

      if (values.type === 'url') {
        if (values.websiteUrl.trim() === '') {
          ctx.addIssue({ code: 'custom', path: ['websiteUrl'], message: 'Enter a web address' })
        } else if (!z.url().safeParse(values.websiteUrl.trim()).success) {
          ctx.addIssue({
            code: 'custom',
            path: ['websiteUrl'],
            message: 'Enter a valid web address',
          })
        }
      }

      if (
        values.type === 'document' &&
        !options.hasExistingSource &&
        values.documentFileName.trim() === ''
      ) {
        ctx.addIssue({
          code: 'custom',
          path: ['documentFileName'],
          message: 'Choose a file to upload',
        })
      }

      if (values.effectiveDate && values.expirationDate && values.expirationDate <= values.effectiveDate) {
        ctx.addIssue({
          code: 'custom',
          path: ['expirationDate'],
          message: 'Expiration must be after the effective date',
        })
      }
    })
}

/**
 * The three statuses PRD §16.4's toggle can never set directly — Processing,
 * Needs review, and Error are things the system decides, not something an
 * administrator ticks their way back into. Exported once so `KnowledgeForm`
 * and `KnowledgeEditorPage` decide whether to show the "the system set this"
 * note off the same list `resolveKnowledgeStatus` actually preserves, rather
 * than each keeping its own copy that could drift from it.
 */
export const SYSTEM_SET_KNOWLEDGE_STATUSES: KnowledgeStatus[] = [
  'processing',
  'needs_review',
  'error',
]

/**
 * PRD §16.4's "Active / inactive" toggle over five statuses. `active` is the
 * whole story going forward for a manually-authored item; turning the toggle
 * off preserves a system-set status instead of overwriting it with Disabled.
 * A newly uploaded document overrides the toggle entirely — nothing is
 * editable until the upload has been read, so the toggle cannot force it
 * straight to Active.
 */
export function resolveKnowledgeStatus(params: {
  active: boolean
  type: KnowledgeType | ''
  isNewDocumentUpload: boolean
  previousStatus?: KnowledgeStatus
}): KnowledgeStatus {
  if (params.isNewDocumentUpload) return 'processing'
  if (params.active) return 'active'

  if (params.previousStatus && SYSTEM_SET_KNOWLEDGE_STATUSES.includes(params.previousStatus)) {
    return params.previousStatus
  }
  return 'disabled'
}

/** `2026-01-15T00:00:00.000Z` → `2026-01-15`, what a native date input needs. */
function isoToDateInput(iso?: string): string {
  return iso ? iso.slice(0, 10) : ''
}

/** The inverse: midnight UTC on the chosen day, or undefined for a blank field. */
function dateInputToIso(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined
}

export function emptyKnowledgeFormValues(seedType?: KnowledgeType): KnowledgeFormValues {
  return {
    title: '',
    type: seedType ?? '',
    category: '',
    content: '',
    tagsText: '',
    active: true,
    effectiveDate: '',
    expirationDate: '',
    websiteUrl: '',
    documentFileName: '',
  }
}

/** An existing item's fields, laid out as the form's controls expect them. */
export function itemToFormValues(item: KnowledgeItem): KnowledgeFormValues {
  return {
    title: item.title,
    type: item.type,
    category: item.category ?? '',
    content: item.content ?? '',
    tagsText: item.tags.join(', '),
    active: item.status === 'active',
    effectiveDate: isoToDateInput(item.effectiveDate),
    expirationDate: isoToDateInput(item.expirationDate),
    // Only a url item's source belongs in this field — a document's source is
    // a filename, not something to edit as text, and every other type's
    // source is "Manual entry".
    websiteUrl: item.type === 'url' ? item.source : '',
    // A file input can never be pre-filled from a filename; editing a
    // document without choosing a new one leaves this blank and keeps the
    // original source.
    documentFileName: '',
  }
}

export interface KnowledgeFormOutput {
  title: string
  type: KnowledgeType
  category?: string
  content?: string
  tags: string[]
  status: KnowledgeStatus
  source?: string
  effectiveDate?: string
  expirationDate?: string
}

/**
 * The submitted form, turned into what `knowledgeService.create`/`update`
 * expect. `original` is omitted for a new item and supplied for an edit — it
 * is what lets a status get preserved and a document's source survive an edit
 * that didn't touch the file.
 */
export function knowledgeFormValuesToOutput(
  values: KnowledgeFormValues,
  original?: KnowledgeItem,
): KnowledgeFormOutput {
  const type = values.type as KnowledgeType
  const tags = values.tagsText
    .split(',')
    .map((tag) => tag.trim())
    .filter((tag) => tag !== '')

  const isNewDocumentUpload = type === 'document' && values.documentFileName.trim() !== ''

  // Every branch falls back to the original's source on an edit — only a
  // brand-new item (no `original`) can legitimately end up with none, which
  // the service then defaults to "Manual entry". Object.assign(item, patch)
  // in the mock service copies an `undefined` key as readily as any other
  // value, so leaving a branch that produces bare `undefined` on an edit
  // would blank the item's real source rather than leave it alone.
  const source =
    type === 'url'
      ? values.websiteUrl.trim()
      : type === 'document'
        ? values.documentFileName.trim() || original?.source
        : original?.source

  return {
    title: values.title.trim(),
    type,
    category: values.category.trim() || undefined,
    content: values.content.trim() || undefined,
    tags,
    status: resolveKnowledgeStatus({
      active: values.active,
      type,
      isNewDocumentUpload,
      previousStatus: original?.status,
    }),
    source,
    effectiveDate: dateInputToIso(values.effectiveDate),
    expirationDate: dateInputToIso(values.expirationDate),
  }
}
