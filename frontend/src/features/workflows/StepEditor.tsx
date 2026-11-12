import { useFormContext } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { Select } from '@/components/ui/Select'
import type { SelectOption } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { useConfirm } from '@/components/ui/useConfirm'
import {
  WORKFLOW_STEP_TYPE_LABELS,
  WORKFLOW_STEP_TYPES,
  WORKFLOW_TOOL_LABELS,
  WORKFLOW_TOOLS,
} from '@/types'

import type { WorkflowStepsFormValues } from './workflowStepFormSchema'

const TYPE_OPTIONS: SelectOption[] = WORKFLOW_STEP_TYPES.map((type) => ({
  value: type,
  label: WORKFLOW_STEP_TYPE_LABELS[type],
}))

const TOOL_OPTIONS: SelectOption[] = WORKFLOW_TOOLS.map((tool) => ({
  value: tool,
  label: WORKFLOW_TOOL_LABELS[tool],
}))

export interface StepEditorProps {
  /** The step's position in the shared form's `steps` array, or `null` while none is selected. */
  index: number | null
  onDelete: () => void
}

/**
 * US-8.2's step configuration panel — PRD §15.4's seven fields for whichever
 * step `StepList` has selected. Reads and writes through `useFormContext`
 * under `steps.${index}`, the same convention `BusinessProfileFields` uses,
 * so it saves and publishes together with the rest of the page's one form.
 */
export function StepEditor({ index, onDelete }: StepEditorProps) {
  const { watch } = useFormContext<WorkflowStepsFormValues>()

  if (index === null) {
    return (
      <Panel data-testid="step-editor-panel">
        <PanelHeader title="Step configuration" />
        <div className="p-4 text-sm text-ink-secondary">
          Select a step to edit it, or add a new one.
        </div>
      </Panel>
    )
  }

  // Keyed by both the step's own id and its index so the fields remount
  // when the selection moves to a different step, or a step moves or is
  // deleted and a different one lands on the same index.
  return (
    <StepFields
      key={`${watch(`steps.${index}.id`)}:${index}`}
      index={index}
      onDelete={onDelete}
    />
  )
}

interface StepFieldsProps {
  index: number
  onDelete: () => void
}

function StepFields({ index, onDelete }: StepFieldsProps) {
  const {
    register,
    watch,
    formState: { errors },
  } = useFormContext<WorkflowStepsFormValues>()
  const confirm = useConfirm()

  const step = watch(`steps.${index}`)
  const stepErrors = errors.steps?.[index]

  async function handleDelete() {
    const confirmed = await confirm({
      title: `Delete "${step.name || 'this step'}"?`,
      description: 'Concierge will no longer follow this step.',
      confirmLabel: 'Delete',
      tone: 'danger',
    })
    if (confirmed) onDelete()
  }

  return (
    <Panel data-testid="step-editor-panel">
      <PanelHeader
        title="Step configuration"
        action={
          <Button variant="danger" size="sm" onClick={handleDelete}>
            Delete step
          </Button>
        }
      />
      <div className="space-y-1 p-4">
        <Field label="Name" htmlFor={`step-${index}-name`} error={stepErrors?.name?.message}>
          <Input {...register(`steps.${index}.name`)} />
        </Field>
        <Field label="Description" htmlFor={`step-${index}-description`}>
          <Textarea rows={2} {...register(`steps.${index}.description`)} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Type" htmlFor={`step-${index}-type`}>
            <Select {...register(`steps.${index}.type`)} options={TYPE_OPTIONS} />
          </Field>
          <Field label="Tool" htmlFor={`step-${index}-tool`}>
            <Select
              {...register(`steps.${index}.tool`)}
              options={TOOL_OPTIONS}
              placeholder="No tool"
            />
          </Field>
        </div>
        <Field label="Error behavior" htmlFor={`step-${index}-error`}>
          <Textarea rows={2} {...register(`steps.${index}.errorBehavior`)} />
        </Field>
        <Field label="Escalation behavior" htmlFor={`step-${index}-escalation`}>
          <Textarea rows={2} {...register(`steps.${index}.escalationBehavior`)} />
        </Field>
      </div>
    </Panel>
  )
}
