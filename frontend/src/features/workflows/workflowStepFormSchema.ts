import { z } from 'zod'

import { WORKFLOW_STEP_TYPES, WORKFLOW_TOOLS } from '@/types'
import type { Workflow, WorkflowStep, WorkflowTool } from '@/types'

export interface StepFormValues {
  /** Client-generated for a step added in this session; the server id once persisted. */
  id: string
  name: string
  description: string
  type: WorkflowStep['type']
  /** `''` means "no tool". */
  tool: string
  errorBehavior: string
  escalationBehavior: string
}

export interface WorkflowStepsFormValues {
  appliesWhen: string
  steps: StepFormValues[]
}

const stepSchema = z.object({
  id: z.string(),
  name: z.string().trim().min(1, 'Enter a step name'),
  description: z.string(),
  type: z.enum(WORKFLOW_STEP_TYPES),
  tool: z.string(),
  errorBehavior: z.string(),
  escalationBehavior: z.string(),
})

export const workflowStepsFormSchema = z.object({
  appliesWhen: z.string(),
  steps: z.array(stepSchema),
})

function isWorkflowTool(value: string): value is WorkflowTool {
  return (WORKFLOW_TOOLS as readonly string[]).includes(value)
}

/** A workflow's steps, laid out as the editor's controls expect them. */
export function workflowToFormValues(workflow: Workflow): WorkflowStepsFormValues {
  return {
    appliesWhen: workflow.appliesWhen ?? '',
    steps: workflow.steps.map((step) => ({
      id: step.id,
      name: step.name,
      description: step.description ?? '',
      type: step.type,
      tool: step.tool ?? '',
      errorBehavior: step.errorBehavior ?? '',
      escalationBehavior: step.escalationBehavior ?? '',
    })),
  }
}

/** The submitted form, turned into what `workflowService.saveDraft` expects. */
export function formValuesToSteps(values: WorkflowStepsFormValues): WorkflowStep[] {
  return values.steps.map((step) => ({
    id: step.id,
    name: step.name.trim(),
    description: step.description.trim() || undefined,
    type: step.type,
    tool: isWorkflowTool(step.tool) ? step.tool : undefined,
    errorBehavior: step.errorBehavior.trim() || undefined,
    escalationBehavior: step.escalationBehavior.trim() || undefined,
  }))
}

/** A freshly added step: blank, with the first step type and a client-generated id. */
export function emptyStep(): StepFormValues {
  return {
    id: crypto.randomUUID(),
    name: '',
    description: '',
    type: WORKFLOW_STEP_TYPES[0],
    tool: '',
    errorBehavior: '',
    escalationBehavior: '',
  }
}
