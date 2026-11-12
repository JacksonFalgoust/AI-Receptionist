import { describe, expect, it } from 'vitest'

import type { Workflow } from '@/types'

import {
  emptyStep,
  formValuesToSteps,
  workflowStepsFormSchema,
  workflowToFormValues,
} from './workflowStepFormSchema'
import type { WorkflowStepsFormValues } from './workflowStepFormSchema'

const baseValues: WorkflowStepsFormValues = {
  appliesWhen: 'when a caller asks to book',
  steps: [
    {
      id: 'wfs_1',
      name: 'Check availability',
      description: 'Scheduling system, offer alternatives.',
      type: 'look_up',
      tool: 'checkAvailability',
      errorBehavior: 'Escalate to a team member',
      escalationBehavior: '',
    },
  ],
}

const baseWorkflow: Workflow = {
  id: 'wf_0001',
  organizationId: 'org_horizon',
  name: 'Book an appointment',
  description: 'Books a client appointment.',
  appliesWhen: 'when a caller asks to book',
  status: 'active',
  version: 4,
  executionCount: 12,
  lastUpdatedAt: '2026-09-02T14:12:00.000Z',
  steps: [
    {
      id: 'wfs_1',
      name: 'Check availability',
      description: 'Scheduling system, offer alternatives.',
      type: 'look_up',
      tool: 'checkAvailability',
      errorBehavior: 'Escalate to a team member',
    },
    { id: 'wfs_2', name: 'End the call', type: 'end' },
  ],
}

describe('workflowStepsFormSchema', () => {
  it('requires a name on every step', () => {
    const result = workflowStepsFormSchema.safeParse({
      steps: [{ ...baseValues.steps[0], name: '  ' }],
    })
    expect(result.success).toBe(false)
  })

  it('accepts an empty step list', () => {
    expect(workflowStepsFormSchema.safeParse({ appliesWhen: '', steps: [] }).success).toBe(true)
  })

  it('accepts a fully filled-in step', () => {
    expect(workflowStepsFormSchema.safeParse(baseValues).success).toBe(true)
  })
})

describe('workflowToFormValues', () => {
  it('carries every step field into the form shape', () => {
    const values = workflowToFormValues(baseWorkflow)
    expect(values.steps[0]).toMatchObject({
      id: 'wfs_1',
      name: 'Check availability',
      description: 'Scheduling system, offer alternatives.',
      type: 'look_up',
      tool: 'checkAvailability',
      errorBehavior: 'Escalate to a team member',
      escalationBehavior: '',
    })
    expect(values.appliesWhen).toBe('when a caller asks to book')
  })

  it('gives an optional field with no value an empty string, not undefined', () => {
    const values = workflowToFormValues(baseWorkflow)
    expect(values.steps[1].description).toBe('')
    expect(values.steps[1].tool).toBe('')
  })
})

describe('formValuesToSteps', () => {
  it('round-trips a step\'s tool', () => {
    const [step] = formValuesToSteps(baseValues)
    expect(step.tool).toBe('checkAvailability')
  })

  it('trims a step name and drops blank optional fields back to undefined', () => {
    const [step] = formValuesToSteps({
      ...baseValues,
      steps: [
        {
          ...baseValues.steps[0],
          name: '  Check availability  ',
          description: '   ',
          tool: '',
          errorBehavior: '  ',
          escalationBehavior: '',
        },
      ],
    })
    expect(step).toMatchObject({
      name: 'Check availability',
      description: undefined,
      tool: undefined,
      errorBehavior: undefined,
      escalationBehavior: undefined,
    })
  })
})

describe('emptyStep', () => {
  it('starts with no tool', () => {
    expect(emptyStep().tool).toBe('')
  })

  it('starts blank with the first step type and a fresh id', () => {
    const a = emptyStep()
    const b = emptyStep()
    expect(a.name).toBe('')
    expect(a.id).not.toBe(b.id)
  })
})
