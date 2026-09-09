import { nextId, sortByDesc } from '@/mocks/query'
import { MOCK_ORGANIZATION_ID } from '@/mocks/session'
import { store } from '@/mocks/store'
import type { Id, Workflow } from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

export interface CreateWorkflowInput {
  name: string
  description?: string
}

export type WorkflowPatch = Partial<Pick<Workflow, 'name' | 'description' | 'steps'>>

/** PRD §15 / US-8.1, US-8.2. */
export interface WorkflowService {
  list(): Promise<Workflow[]>
  get(id: Id): Promise<Workflow>
  create(input: CreateWorkflowInput): Promise<Workflow>
  /** Edits the draft. Never changes `status` or `version` — only `publish` does. */
  saveDraft(id: Id, patch: WorkflowPatch): Promise<Workflow>
  publish(id: Id): Promise<Workflow>
  remove(id: Id): Promise<void>
}

function requireWorkflow(id: Id): Workflow {
  const workflow = store.workflows.find((item) => item.id === id)
  if (!workflow) {
    throw new AppError({
      kind: 'not_found',
      title: 'Workflow not found',
      description: 'That workflow no longer exists or was deleted.',
      actions: [{ label: 'Back to workflows', href: '/concierge/workflows' }],
    })
  }
  return workflow
}

const mockWorkflowService: WorkflowService = {
  async list() {
    await delay()
    return sortByDesc(store.workflows, (workflow) => workflow.lastUpdatedAt)
  },

  async get(id) {
    await delay()
    return requireWorkflow(id)
  },

  async create(input) {
    await delay()
    const workflow: Workflow = {
      id: nextId('wf'),
      organizationId: MOCK_ORGANIZATION_ID,
      name: input.name,
      description: input.description,
      status: 'draft',
      version: 1,
      steps: [],
      executionCount: 0,
      lastUpdatedAt: new Date().toISOString(),
    }
    store.workflows.push(workflow)
    return workflow
  },

  async saveDraft(id, patch) {
    await delay()
    const workflow = requireWorkflow(id)
    const index = store.workflows.findIndex((w) => w.id === id)
    const updated = {
      ...workflow,
      ...patch,
      lastUpdatedAt: new Date().toISOString(),
    }
    store.workflows[index] = updated
    return updated
  },

  async publish(id) {
    await delay()
    const workflow = requireWorkflow(id)
    const index = store.workflows.findIndex((w) => w.id === id)
    const published = {
      ...workflow,
      status: 'active' as const,
      version: workflow.version + 1,
      lastUpdatedAt: new Date().toISOString(),
    }
    store.workflows[index] = published
    return published
  },

  async remove(id) {
    await delay()
    requireWorkflow(id)
    store.workflows = store.workflows.filter((workflow) => workflow.id !== id)
  },
}

const httpWorkflowService: WorkflowService = {
  list: () => http.get<Workflow[]>('/workflows'),
  get: (id) => http.get<Workflow>(`/workflows/${id}`),
  create: (input) => http.post<Workflow>('/workflows', input),
  saveDraft: (id, patch) => http.patch<Workflow>(`/workflows/${id}`, patch),
  publish: (id) => http.post<Workflow>(`/workflows/${id}/publish`),
  remove: (id) => http.delete<void>(`/workflows/${id}`),
}

export const workflowService: WorkflowService = USE_MOCKS
  ? mockWorkflowService
  : httpWorkflowService
