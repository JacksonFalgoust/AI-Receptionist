import { useFieldArray, useFormContext } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { Select } from '@/components/ui/Select'
import type { SelectOption } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { useConfirm } from '@/components/ui/useConfirm'
import { withCurrentValue } from '@/lib/selectOptions'
import { WORKFLOW_STEP_TYPE_LABELS, WORKFLOW_STEP_TYPES } from '@/types'

import type { WorkflowStepsFormValues } from './workflowStepFormSchema'

const TYPE_OPTIONS: SelectOption[] = WORKFLOW_STEP_TYPES.map((type) => ({
  value: type,
  label: WORKFLOW_STEP_TYPE_LABELS[type],
}))

export interface StepEditorProps {
  /** The step's position in the shared form's `steps` array, or `null` while none is selected. */
  index: number | null
  integrationOptions: SelectOption[]
  onDelete: () => void
}

/**
 * US-8.2's step configuration panel — PRD §15.4's seven fields for whichever
 * step `StepList` has selected. Reads and writes through `useFormContext`
 * under `steps.${index}`, the same convention `BusinessProfileFields` uses,
 * so it saves and publishes together with the rest of the page's one form.
 */
export function StepEditor({ index, integrationOptions, onDelete }: StepEditorProps) {
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

  // Keyed by the step's own id rather than `index`: `useFieldArray` below
  // does not support a dynamically-changing array path on one mounted
  // instance, so switching the selection must remount it. Keying by index
  // alone would miss the case where a step is deleted and the fallback
  // selection lands on the same index a different step now occupies.
  return (
    <StepFields
      key={watch(`steps.${index}.id`)}
      index={index}
      integrationOptions={integrationOptions}
      onDelete={onDelete}
    />
  )
}

interface StepFieldsProps {
  index: number
  integrationOptions: SelectOption[]
  onDelete: () => void
}

function StepFields({ index, integrationOptions, onDelete }: StepFieldsProps) {
  const {
    register,
    watch,
    control,
    formState: { errors },
  } = useFormContext<WorkflowStepsFormValues>()
  const confirm = useConfirm()

  const configuration = useFieldArray({
    control,
    name: `steps.${index}.configuration`,
  })

  const step = watch(`steps.${index}`)
  const stepErrors = errors.steps?.[index]
  const requiredIntegrationOptions = withCurrentValue(
    integrationOptions,
    step.requiredIntegrationId,
  )

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
          <Field label="Required integration" htmlFor={`step-${index}-integration`}>
            <Select
              {...register(`steps.${index}.requiredIntegrationId`)}
              options={requiredIntegrationOptions}
              placeholder="No required integration"
            />
          </Field>
        </div>
        <Field label="Error behavior" htmlFor={`step-${index}-error`}>
          <Textarea rows={2} {...register(`steps.${index}.errorBehavior`)} />
        </Field>
        <Field label="Escalation behavior" htmlFor={`step-${index}-escalation`}>
          <Textarea rows={2} {...register(`steps.${index}.escalationBehavior`)} />
        </Field>

        <fieldset className="mb-4">
          <legend className="mb-1.5 block text-sm font-semibold text-ink">Configuration</legend>
          <div className="space-y-2">
            {configuration.fields.map((field, rowIndex) => {
              const rowError = stepErrors?.configuration?.[rowIndex]?.key?.message
              return (
                <div key={field.id}>
                  <div className="flex gap-2">
                    <Input
                      aria-label="Configuration key"
                      placeholder="Key"
                      invalid={Boolean(rowError)}
                      {...register(`steps.${index}.configuration.${rowIndex}.key`)}
                    />
                    <Input
                      aria-label="Configuration value"
                      placeholder="Value"
                      {...register(`steps.${index}.configuration.${rowIndex}.value`)}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove configuration row ${rowIndex + 1}`}
                      onClick={() => configuration.remove(rowIndex)}
                    >
                      Remove
                    </Button>
                  </div>
                  {rowError ? <p className="mt-1 text-xs text-danger">{rowError}</p> : null}
                </div>
              )
            })}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() => configuration.append({ key: '', value: '' })}
          >
            Add configuration
          </Button>
        </fieldset>
      </div>
    </Panel>
  )
}
