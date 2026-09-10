import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FormProvider, useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'

import { Breadcrumb } from '@/components/ui/Breadcrumb'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import type { SelectOption } from '@/components/ui/Select'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { StepEditor } from '@/features/workflows/StepEditor'
import { StepList } from '@/features/workflows/StepList'
import {
  emptyStep,
  formValuesToSteps,
  workflowStepsFormSchema,
  workflowToFormValues,
} from '@/features/workflows/workflowStepFormSchema'
import type { WorkflowStepsFormValues } from '@/features/workflows/workflowStepFormSchema'
import { statusTone } from '@/lib/statusTone'
import { paths } from '@/routes/paths'
import { toAppError } from '@/services/errors'
import { integrationService } from '@/services/integrationService'
import { workflowService } from '@/services/workflowService'
import type { Workflow } from '@/types'

/**
 * US-8.2. `id` always resolves — `paths.workflow()` only matches a route with
 * one — so `workflowService.get` raising its own `not_found` AppError (routed
 * through `QueryBoundary`) covers the "doesn't exist" case, the same pattern
 * `KnowledgeEditorPage` uses.
 */
export function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>()

  const detailKey = ['workflows', 'detail', id]
  const query = useQuery({
    queryKey: detailKey,
    queryFn: () => workflowService.get(id!),
  })

  const integrationsQuery = useQuery({
    queryKey: ['integrations'],
    queryFn: () => integrationService.list(),
  })
  const integrationOptions: SelectOption[] = (integrationsQuery.data ?? []).map((integration) => ({
    value: integration.id,
    label: integration.name,
  }))

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-3">
        <Breadcrumb
          items={[
            { label: 'Workflows', href: paths.workflows },
            { label: query.data?.name ?? 'Workflow' },
          ]}
        />
      </div>
      <QueryBoundary query={query} skeletonRows={8}>
        {(workflow) => (
          <WorkflowStepsForm
            workflow={workflow}
            detailKey={detailKey}
            integrationOptions={integrationOptions}
          />
        )}
      </QueryBoundary>
    </div>
  )
}

function WorkflowStepsForm({
  workflow,
  detailKey,
  integrationOptions,
}: {
  workflow: Workflow
  detailKey: unknown[]
  integrationOptions: SelectOption[]
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const [selectedStepId, setSelectedStepId] = useState<string | null>(
    () => workflow.steps[0]?.id ?? null,
  )

  const form = useForm<WorkflowStepsFormValues>({
    defaultValues: workflowToFormValues(workflow),
    resolver: zodResolver(workflowStepsFormSchema),
  })

  const save = useMutation({
    mutationFn: async ({
      values,
      thenPublish,
    }: {
      values: WorkflowStepsFormValues
      thenPublish: boolean
    }) => {
      // Publish always saves what's on screen first, so what gets published
      // is never a stale draft from before the admin's last edit.
      const saved = await workflowService.saveDraft(workflow.id, {
        steps: formValuesToSteps(values),
      })
      return thenPublish ? workflowService.publish(workflow.id) : saved
    },
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(detailKey, updated)
      queryClient.setQueryData<Workflow[]>(['workflows'], (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)),
      )
      form.reset(workflowToFormValues(updated))
      toast.show(variables.thenPublish ? 'Workflow published.' : 'Draft saved.', {
        tone: 'success',
      })
    },
    onError: (error) => {
      toast.show(toAppError(error).description, { tone: 'danger' })
    },
  })

  function onInvalid() {
    toast.show('Fix the highlighted step before saving.', { tone: 'danger' })
  }

  const handleSaveDraft = form.handleSubmit((values) => {
    save.mutate({ values, thenPublish: false })
  }, onInvalid)

  const handlePublish = form.handleSubmit(async (values) => {
    if (values.steps.length === 0) {
      toast.show('Add at least one step before publishing.', { tone: 'danger' })
      return
    }
    const confirmed = await confirm({
      title: 'Publish this workflow?',
      description: 'Concierge will immediately use these steps for new conversations.',
      confirmLabel: 'Publish',
    })
    if (!confirmed) return
    save.mutate({ values, thenPublish: true })
  }, onInvalid)

  function handleAddStep() {
    const step = emptyStep()
    form.setValue('steps', [...form.getValues('steps'), step], { shouldDirty: true })
    setSelectedStepId(step.id)
  }

  function handleDeleteStep(stepId: string) {
    const remaining = form.getValues('steps').filter((step) => step.id !== stepId)
    form.setValue('steps', remaining, { shouldDirty: true })
    if (selectedStepId === stepId) {
      setSelectedStepId(remaining[0]?.id ?? null)
    }
  }

  function handleMoveStep(stepId: string, direction: 'up' | 'down') {
    const current = form.getValues('steps')
    const index = current.findIndex((step) => step.id === stepId)
    const swapWith = direction === 'up' ? index - 1 : index + 1
    if (index === -1 || swapWith < 0 || swapWith >= current.length) return

    const next = [...current]
    ;[next[index], next[swapWith]] = [next[swapWith], next[index]]
    form.setValue('steps', next, { shouldDirty: true })
  }

  const steps = form.watch('steps')
  const selectedIndex = steps.findIndex((step) => step.id === selectedStepId)

  const isSavingDraft = save.isPending && save.variables?.thenPublish === false
  const isPublishing = save.isPending && save.variables?.thenPublish === true

  return (
    <FormProvider {...form}>
      <PageHeader
        title={workflow.name}
        description={`${statusTone(workflow.status).label} · v${workflow.version} · ${workflow.executionCount.toLocaleString('en-US')} executions`}
        actions={
          <>
            <Button
              variant="ghost"
              isLoading={isSavingDraft}
              disabled={save.isPending}
              onClick={handleSaveDraft}
            >
              Save draft
            </Button>
            <Button isLoading={isPublishing} disabled={save.isPending} onClick={handlePublish}>
              Publish
            </Button>
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <StepList
          steps={steps}
          selectedId={selectedStepId}
          onSelect={setSelectedStepId}
          onAdd={handleAddStep}
          onMove={handleMoveStep}
        />
        <StepEditor
          index={selectedIndex === -1 ? null : selectedIndex}
          integrationOptions={integrationOptions}
          onDelete={() => {
            if (selectedIndex !== -1) handleDeleteStep(steps[selectedIndex].id)
          }}
        />
      </div>
    </FormProvider>
  )
}
