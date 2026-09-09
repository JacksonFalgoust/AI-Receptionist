import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { StatusPill } from '@/components/ui/StatusPill'
import { Textarea } from '@/components/ui/Textarea'
import { Toggle } from '@/components/ui/Toggle'
import { KNOWLEDGE_TYPES, knowledgeTypeLabel } from '@/lib/knowledgeLabels'
import type { KnowledgeStatus } from '@/types'

import { knowledgeFormSchema } from './knowledgeFormSchema'
import type { KnowledgeFormValues } from './knowledgeFormSchema'

const TYPE_OPTIONS = KNOWLEDGE_TYPES.map((type) => ({ value: type, label: knowledgeTypeLabel(type) }))

/** The three statuses PRD §16.4's toggle can never set directly — see `resolveKnowledgeStatus`. */
const SYSTEM_SET_STATUSES: KnowledgeStatus[] = ['processing', 'needs_review', 'error']

export interface KnowledgeFormProps {
  defaultValues: KnowledgeFormValues
  /** True once an item already has a file on record — a document edit then never has to require a new one. */
  hasExistingSource: boolean
  /** The filename already on record, shown so replacing it is a choice rather than a mystery. */
  existingSource?: string
  /** Present only when the item's real status is one the system set, not the administrator. */
  previousStatus?: KnowledgeStatus
  isSubmitting?: boolean
  submitLabel: string
  onSubmit: (values: KnowledgeFormValues) => void
}

/**
 * US-5.2's fields. Purely presentational — knows nothing about services,
 * routing, or toasts — so `KnowledgeEditorPage` owns every side effect and
 * this stays easy to test in isolation.
 */
export function KnowledgeForm({
  defaultValues,
  hasExistingSource,
  existingSource,
  previousStatus,
  isSubmitting = false,
  submitLabel,
  onSubmit,
}: KnowledgeFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<KnowledgeFormValues>({
    defaultValues,
    resolver: zodResolver(knowledgeFormSchema({ hasExistingSource })),
  })

  const type = watch('type')
  const documentFileName = watch('documentFileName')

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="max-w-2xl space-y-1">
      <Field label="Title" htmlFor="title" error={errors.title?.message}>
        <Input {...register('title')} />
      </Field>

      <Field label="Type" htmlFor="type" error={errors.type?.message}>
        <Select
          {...register('type')}
          options={TYPE_OPTIONS}
          placeholder="Select a type"
        />
      </Field>

      <Field label="Category" htmlFor="category">
        <Input {...register('category')} />
      </Field>

      {type === 'url' ? (
        <Field
          label="Website address"
          htmlFor="websiteUrl"
          error={errors.websiteUrl?.message}
          description="Concierge reads this page's content once it processes."
        >
          <Input type="url" placeholder="https://example.com/page" {...register('websiteUrl')} />
        </Field>
      ) : null}

      {type === 'document' ? (
        <Field
          label="File"
          htmlFor="documentFile"
          error={errors.documentFileName?.message}
          description={
            hasExistingSource && !documentFileName && existingSource
              ? `Current file: ${existingSource}. Choose a new one to replace it.`
              : undefined
          }
        >
          <input
            id="documentFile"
            type="file"
            className="block w-full text-sm text-ink-secondary file:mr-3 file:rounded-sm file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm file:font-semibold"
            onChange={(event) => {
              const file = event.target.files?.[0]
              setValue('documentFileName', file?.name ?? '', { shouldValidate: true })
            }}
          />
        </Field>
      ) : null}

      <Field
        label="Content"
        htmlFor="content"
        error={errors.content?.message}
        description={
          type === 'document' || type === 'url'
            ? 'Optional — Concierge reads this from the file or page once processed.'
            : undefined
        }
      >
        <Textarea rows={5} {...register('content')} />
      </Field>

      <Field label="Tags" htmlFor="tagsText" description="Comma-separated, e.g. billing, refunds">
        <Input {...register('tagsText')} />
      </Field>

      <div className="mb-4">
        <Toggle label="Active" {...register('active')} />
        {previousStatus && SYSTEM_SET_STATUSES.includes(previousStatus) ? (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-secondary">
            <StatusPill status={previousStatus} />
            Concierge set this status; turning Active on replaces it. Leaving Active off keeps it as
            it is.
          </p>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Effective date" htmlFor="effectiveDate">
          <Input type="date" {...register('effectiveDate')} />
        </Field>
        <Field
          label="Expiration date"
          htmlFor="expirationDate"
          error={errors.expirationDate?.message}
        >
          <Input type="date" {...register('expirationDate')} />
        </Field>
      </div>

      <Button type="submit" isLoading={isSubmitting} className="mt-2">
        {submitLabel}
      </Button>
    </form>
  )
}
