import { z } from 'zod'

import { WORKFLOW_STEP_TYPES } from '@/types'
import type { Workflow, WorkflowStep } from '@/types'

export interface ConfigurationRowValues {
  key: string
  value: string
}

export interface StepFormValues {
  /** Client-generated for a step added in this session; the server id once persisted. */
  id: string
  name: string
  description: string
  type: WorkflowStep['type']
  /** `''` means "no required integration". */
  requiredIntegrationId: string
  errorBehavior: string
  escalationBehavior: string
  /** `WorkflowStep.configuration`'s `Record<string, string>`, laid out as editable rows. */
  configuration: ConfigurationRowValues[]
}

export interface WorkflowStepsFormValues {
  steps: StepFormValues[]
}

const configurationRowSchema = z.object({
  key: z.string(),
  value: z.string(),
})

const stepSchema = z
  .object({
    id: z.string(),
    name: z.string().trim().min(1, 'Enter a step name'),
    description: z.string(),
    type: z.enum(WORKFLOW_STEP_TYPES),
    requiredIntegrationId: z.string(),
    errorBehavior: z.string(),
    escalationBehavior: z.string(),
    configuration: z.array(configurationRowSchema),
  })
  .superRefine((step, ctx) => {
    // A duplicate key would otherwise collapse silently in `formValuesToSteps`
    // — the record it builds can only hold one value per key — so this is
    // caught here instead, before the row the admin can still see disappears
    // with nothing to explain why.
    const seen = new Set<string>()
    step.configuration.forEach((row, index) => {
      const key = row.key.trim()
      if (key === '') return
      if (seen.has(key)) {
        ctx.addIssue({
          code: 'custom',
          path: ['configuration', index, 'key'],
          message: 'Configuration keys must be unique.',
        })
      }
      seen.add(key)
    })
  })

export const workflowStepsFormSchema = z.object({
  steps: z.array(stepSchema),
})

/** A workflow's steps, laid out as the editor's controls expect them. */
export function workflowToFormValues(workflow: Workflow): WorkflowStepsFormValues {
  return {
    steps: workflow.steps.map((step) => ({
      id: step.id,
      name: step.name,
      description: step.description ?? '',
      type: step.type,
      requiredIntegrationId: step.requiredIntegrationId ?? '',
      errorBehavior: step.errorBehavior ?? '',
      escalationBehavior: step.escalationBehavior ?? '',
      configuration: Object.entries(step.configuration ?? {}).map(([key, value]) => ({
        key,
        value,
      })),
    })),
  }
}

/** The submitted form, turned into what `workflowService.saveDraft` expects. */
export function formValuesToSteps(values: WorkflowStepsFormValues): WorkflowStep[] {
  return values.steps.map((step) => {
    const configuration = step.configuration.reduce<Record<string, string>>((acc, row) => {
      const key = row.key.trim()
      if (key !== '') acc[key] = row.value
      return acc
    }, {})

    return {
      id: step.id,
      name: step.name.trim(),
      description: step.description.trim() || undefined,
      type: step.type,
      requiredIntegrationId: step.requiredIntegrationId || undefined,
      errorBehavior: step.errorBehavior.trim() || undefined,
      escalationBehavior: step.escalationBehavior.trim() || undefined,
      configuration: Object.keys(configuration).length > 0 ? configuration : undefined,
    }
  })
}

/** A freshly added step: blank, with the first step type and a client-generated id. */
export function emptyStep(): StepFormValues {
  return {
    id: crypto.randomUUID(),
    name: '',
    description: '',
    type: WORKFLOW_STEP_TYPES[0],
    requiredIntegrationId: '',
    errorBehavior: '',
    escalationBehavior: '',
    configuration: [],
  }
}
