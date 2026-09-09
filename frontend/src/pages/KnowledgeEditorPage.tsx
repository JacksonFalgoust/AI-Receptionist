import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { Breadcrumb } from '@/components/ui/Breadcrumb'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { KnowledgeForm } from '@/features/knowledge/KnowledgeForm'
import {
  emptyKnowledgeFormValues,
  itemToFormValues,
  knowledgeFormValuesToOutput,
  SYSTEM_SET_KNOWLEDGE_STATUSES,
} from '@/features/knowledge/knowledgeFormSchema'
import type { KnowledgeFormValues } from '@/features/knowledge/knowledgeFormSchema'
import { KNOWLEDGE_TYPES } from '@/lib/knowledgeLabels'
import { paths } from '@/routes/paths'
import { knowledgeService } from '@/services/knowledgeService'
import { toAppError } from '@/services/errors'
import type { CreateKnowledgeInput, KnowledgePatch } from '@/services/knowledgeService'
import type { KnowledgeItem, KnowledgeType } from '@/types'

function seedTypeFromParam(value: string | null): KnowledgeType | undefined {
  return (KNOWLEDGE_TYPES as string[]).includes(value ?? '') ? (value as KnowledgeType) : undefined
}

/**
 * US-5.2. Both `/concierge/knowledge/new` and `/concierge/knowledge/:id`
 * render this; `id` tells the two apart. A missing id on the edit route needs
 * no branch of its own — `knowledgeService.get` raises a `not_found` AppError
 * carrying its own way back, and `QueryBoundary` renders it (see
 * `ConversationDetailPage` for the same pattern).
 */
export function KnowledgeEditorPage() {
  const { id } = useParams()
  const isNew = id === undefined
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()

  const detailKey = ['knowledge', 'detail', id]

  const query = useQuery({
    queryKey: detailKey,
    queryFn: () => knowledgeService.get(id!),
    enabled: !isNew,
  })

  // Both mutations return to the library rather than staying on the item —
  // simpler than resyncing the form's defaults from a fresh server response,
  // and matches Delete's own toast-then-back-to-library.
  function afterWrite(message: string) {
    queryClient.invalidateQueries({ queryKey: ['knowledge', 'list'] })
    toast.show(message, { tone: 'success' })
    navigate(paths.knowledge)
  }

  function onError(error: unknown) {
    toast.show(toAppError(error).description, { tone: 'danger' })
  }

  const create = useMutation({
    mutationFn: (input: CreateKnowledgeInput) => knowledgeService.create(input),
    onSuccess: () => afterWrite('Knowledge added.'),
    onError,
  })

  const update = useMutation({
    mutationFn: (patch: KnowledgePatch) => knowledgeService.update(id!, patch),
    onSuccess: () => afterWrite('Knowledge updated.'),
    onError,
  })

  const remove = useMutation({
    mutationFn: () => knowledgeService.remove(id!),
    onSuccess: () => afterWrite('Knowledge deleted.'),
    onError,
  })

  function handleSubmit(values: KnowledgeFormValues, original?: KnowledgeItem) {
    const output = knowledgeFormValuesToOutput(values, original)
    if (isNew) {
      create.mutate(output)
    } else {
      update.mutate(output)
    }
  }

  async function handleDelete(item: KnowledgeItem) {
    const confirmed = await confirm({
      title: `Delete "${item.title}"?`,
      description: 'Concierge will no longer use this information when answering customers.',
      confirmLabel: 'Delete',
      tone: 'danger',
    })
    if (confirmed) remove.mutate()
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-3">
        <Breadcrumb
          items={[
            { label: 'Knowledge', href: paths.knowledge },
            { label: isNew ? 'Add knowledge' : 'Edit knowledge' },
          ]}
        />
      </div>
      <PageHeader
        title={isNew ? 'Add knowledge' : 'Edit knowledge'}
        description={
          isNew
            ? 'Add information Concierge can use when responding to customers.'
            : 'Update this information so Concierge answers with what is true today.'
        }
      />

      {isNew ? (
        <KnowledgeForm
          defaultValues={emptyKnowledgeFormValues(seedTypeFromParam(searchParams.get('type')))}
          hasExistingSource={false}
          submitLabel="Add knowledge"
          isSubmitting={create.isPending}
          onSubmit={(values) => handleSubmit(values)}
        />
      ) : (
        <QueryBoundary query={query} skeletonRows={6}>
          {(item) => (
            <div className="space-y-6">
              <KnowledgeForm
                defaultValues={itemToFormValues(item)}
                hasExistingSource={item.type === 'document'}
                existingSource={item.type === 'document' ? item.source : undefined}
                previousStatus={
                  SYSTEM_SET_KNOWLEDGE_STATUSES.includes(item.status) ? item.status : undefined
                }
                submitLabel="Save changes"
                isSubmitting={update.isPending}
                onSubmit={(values) => handleSubmit(values, item)}
              />
              <div className="border-t border-border pt-4">
                <Button
                  variant="danger"
                  isLoading={remove.isPending}
                  onClick={() => handleDelete(item)}
                >
                  Delete
                </Button>
              </div>
            </div>
          )}
        </QueryBoundary>
      )}
    </div>
  )
}
