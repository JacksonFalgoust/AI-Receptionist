import { nextId, sortByDesc } from '@/mocks/query'
import { MOCK_ORGANIZATION_ID } from '@/mocks/session'
import { store } from '@/mocks/store'
import type { Id, Workflow } from '@/types'

import { delay, isLive } from './config'
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

/**
 * The only field `saveDraft` can legitimately be asked to blank is
 * `description` -- `name` is required and `steps` is always either the
 * complete array or fully absent, never a value meaning "clear it". No
 * current caller sends `description` through saveDraft (WorkflowDetailPage
 * only ever patches `steps`), but the WorkflowPatch type declares
 * `description` as patchable and clearable, so the contract must hold if
 * something does call it -- see frontend/src/services/knowledgeService.ts's
 * identical `normalizePatchForWire` for why this matters: JSON.stringify
 * drops `undefined` keys entirely, and the API's exclude_unset=True PATCH
 * semantics (correctly) read a missing key as "leave alone" rather than
 * "clear it".
 */
function normalizePatchForWire(patch: WorkflowPatch): Record<string, unknown> {
  const normalized: Record<string, unknown> = { ...patch }
  if ('description' in patch && normalized.description === undefined) {
    normalized.description = null
  }
  return normalized
}

const httpWorkflowService: WorkflowService = {
  list: () => http.get<Workflow[]>('/workflows'),
  get: (id) => http.get<Workflow>(`/workflows/${id}`),
  create: (input) => http.post<Workflow>('/workflows', input),
  saveDraft: (id, patch) => http.patch<Workflow>(`/workflows/${id}`, normalizePatchForWire(patch)),
  publish: (id) => http.post<Workflow>(`/workflows/${id}/publish`),
  remove: (id) => http.delete<void>(`/workflows/${id}`),
}

export const workflowService: WorkflowService = isLive('workflows')
  ? httpWorkflowService
  : mockWorkflowService
