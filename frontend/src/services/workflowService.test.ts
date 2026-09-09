import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { workflowService } from './workflowService'

describe('workflowService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists workflows most recently updated first', async () => {
    const workflows = await workflowService.list()
    const times = workflows.map((item) => new Date(item.lastUpdatedAt).getTime())

    expect(workflows.length).toBeGreaterThanOrEqual(6)
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('gets one workflow with its steps', async () => {
    const workflow = await workflowService.get('wf_booking')
    expect(workflow.name).toBe('Book an appointment')
    expect(workflow.steps.length).toBeGreaterThan(0)
  })

  it('creates a workflow as an unpublished draft', async () => {
    const created = await workflowService.create({ name: 'Answer billing questions' })

    expect(created.status).toBe('draft')
    expect(created.version).toBe(1)
    expect(created.executionCount).toBe(0)
    expect(created.steps).toEqual([])
    expect((await workflowService.list()).some((item) => item.id === created.id)).toBe(true)
  })

  it('saveDraft never changes status or version (PRD §13.4)', async () => {
    const before = await workflowService.get('wf_booking')

    const draft = await workflowService.saveDraft('wf_booking', {
      description: 'Updated description.',
    })

    expect(draft.description).toBe('Updated description.')
    expect(draft.status).toBe(before.status)
    expect(draft.version).toBe(before.version)
  })

  it('publish activates the workflow and bumps the version', async () => {
    const before = await workflowService.get('wf_onboarding')
    expect(before.status).toBe('draft')

    const published = await workflowService.publish('wf_onboarding')

    expect(published.status).toBe('active')
    expect(published.version).toBe(before.version + 1)
  })

  it('removes a workflow', async () => {
    await workflowService.remove('wf_survey')
    expect((await workflowService.list()).some((item) => item.id === 'wf_survey')).toBe(false)
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(workflowService.get('wf_missing')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})
