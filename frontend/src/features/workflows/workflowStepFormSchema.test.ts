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
  steps: [
    {
      id: 'wfs_1',
      name: 'Check availability',
      description: 'Scheduling system, offer alternatives.',
      type: 'look_up',
      requiredIntegrationId: 'int_scheduling',
      errorBehavior: 'Escalate to a team member',
      escalationBehavior: '',
      configuration: [{ key: 'timeoutSeconds', value: '30' }],
    },
  ],
}

const baseWorkflow: Workflow = {
  id: 'wf_0001',
  organizationId: 'org_horizon',
  name: 'Book an appointment',
  description: 'Books a client appointment.',
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
      requiredIntegrationId: 'int_scheduling',
      errorBehavior: 'Escalate to a team member',
      configuration: { timeoutSeconds: '30' },
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
    expect(workflowStepsFormSchema.safeParse({ steps: [] }).success).toBe(true)
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
      requiredIntegrationId: 'int_scheduling',
      errorBehavior: 'Escalate to a team member',
      escalationBehavior: '',
    })
  })

  it('turns a step\'s configuration record into rows', () => {
    const values = workflowToFormValues(baseWorkflow)
    expect(values.steps[0].configuration).toEqual([{ key: 'timeoutSeconds', value: '30' }])
  })

  it('gives a step with no configuration an empty row list', () => {
    const values = workflowToFormValues(baseWorkflow)
    expect(values.steps[1].configuration).toEqual([])
  })

  it('gives an optional field with no value an empty string, not undefined', () => {
    const values = workflowToFormValues(baseWorkflow)
    expect(values.steps[1].description).toBe('')
    expect(values.steps[1].requiredIntegrationId).toBe('')
  })
})

describe('formValuesToSteps', () => {
  it('turns configuration rows back into a record', () => {
    const [step] = formValuesToSteps(baseValues)
    expect(step.configuration).toEqual({ timeoutSeconds: '30' })
  })

  it('drops rows with a blank key', () => {
    const [step] = formValuesToSteps({
      steps: [
        {
          ...baseValues.steps[0],
          configuration: [
            { key: 'timeoutSeconds', value: '30' },
            { key: '  ', value: 'ignored' },
          ],
        },
      ],
    })
    expect(step.configuration).toEqual({ timeoutSeconds: '30' })
  })

  it('omits configuration entirely once every row is dropped', () => {
    const [step] = formValuesToSteps({
      steps: [{ ...baseValues.steps[0], configuration: [{ key: '', value: '' }] }],
    })
    expect(step.configuration).toBeUndefined()
  })

  it('trims a step name and drops blank optional fields back to undefined', () => {
    const [step] = formValuesToSteps({
      steps: [
        {
          ...baseValues.steps[0],
          name: '  Check availability  ',
          description: '   ',
          requiredIntegrationId: '',
          errorBehavior: '  ',
          escalationBehavior: '',
        },
      ],
    })
    expect(step).toMatchObject({
      name: 'Check availability',
      description: undefined,
      requiredIntegrationId: undefined,
      errorBehavior: undefined,
      escalationBehavior: undefined,
    })
  })
})

describe('emptyStep', () => {
  it('starts blank with the first step type and a fresh id', () => {
    const a = emptyStep()
    const b = emptyStep()
    expect(a.name).toBe('')
    expect(a.configuration).toEqual([])
    expect(a.id).not.toBe(b.id)
  })
})
