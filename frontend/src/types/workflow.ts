import type { Id, IsoDateTime, TenantScoped } from './common'

/**
 * PRD §15.3. The MVP renders these as a form-driven step list; the same step
 * model is meant to back a future drag-and-drop builder without a rewrite.
 */
export const WORKFLOW_STEP_TYPES = [
  'ask_customer',
  'validate',
  'look_up',
  'make_decision',
  'execute_action',
  'confirm',
  'send_communication',
  'escalate',
  'end',
] as const

export type WorkflowStepType = (typeof WORKFLOW_STEP_TYPES)[number]

export const WORKFLOW_STEP_TYPE_LABELS: Record<WorkflowStepType, string> = {
  ask_customer: 'Ask customer',
  validate: 'Validate information',
  look_up: 'Look up information',
  make_decision: 'Make decision',
  execute_action: 'Execute action',
  confirm: 'Confirm with customer',
  send_communication: 'Send communication',
  escalate: 'Escalate',
  end: 'End workflow',
}

export interface WorkflowStep {
  id: Id
  name: string
  description?: string
  type: WorkflowStepType
  requiredIntegrationId?: Id
  /** What Concierge does when this step fails (PRD §15.4). */
  errorBehavior?: string
  escalationBehavior?: string
  configuration?: Record<string, string>
}

export type WorkflowStatus = 'draft' | 'active' | 'inactive'

export interface Workflow extends TenantScoped {
  id: Id
  name: string
  description?: string
  status: WorkflowStatus
  version: number
  steps: WorkflowStep[]
  executionCount: number
  lastUpdatedAt: IsoDateTime
}
