import { nextId } from '@/mocks/query'
import { MOCK_ORGANIZATION_ID } from '@/mocks/session'
import { store } from '@/mocks/store'
import type { Id, RoutingRule } from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

export type CreateRoutingRuleInput = Omit<RoutingRule, 'id' | 'organizationId'>
export type RoutingRulePatch = Partial<CreateRoutingRuleInput>

/** PRD §18 / US-10.1. */
export interface RoutingService {
  list(): Promise<RoutingRule[]>
  create(input: CreateRoutingRuleInput): Promise<RoutingRule>
  update(id: Id, patch: RoutingRulePatch): Promise<RoutingRule>
  setEnabled(id: Id, enabled: boolean): Promise<RoutingRule>
  remove(id: Id): Promise<void>
}

function requireRule(id: Id): RoutingRule {
  const rule = store.routingRules.find((item) => item.id === id)
  if (!rule) {
    throw new AppError({
      kind: 'not_found',
      title: 'Routing rule not found',
      description: 'That rule no longer exists or was deleted.',
      actions: [{ label: 'Back to routing', href: '/routing' }],
    })
  }
  return rule
}

const mockRoutingService: RoutingService = {
  async list() {
    await delay()
    // Lower number wins when several rules match, so the table reads in the
    // order the rules are actually evaluated.
    return [...store.routingRules].sort((a, b) => a.priority - b.priority)
  },

  async create(input) {
    await delay()
    const rule: RoutingRule = {
      ...input,
      id: nextId('rr'),
      organizationId: MOCK_ORGANIZATION_ID,
    }
    store.routingRules.push(rule)
    return rule
  },

  async update(id, patch) {
    await delay()
    const rule = requireRule(id)
    Object.assign(rule, patch)
    return rule
  },

  async setEnabled(id, enabled) {
    await delay(120)
    const rule = requireRule(id)
    rule.enabled = enabled
    return rule
  },

  async remove(id) {
    await delay()
    requireRule(id)
    store.routingRules = store.routingRules.filter((rule) => rule.id !== id)
  },
}

const httpRoutingService: RoutingService = {
  list: () => http.get<RoutingRule[]>('/routing/rules'),
  create: (input) => http.post<RoutingRule>('/routing/rules', input),
  update: (id, patch) => http.patch<RoutingRule>(`/routing/rules/${id}`, patch),
  setEnabled: (id, enabled) => http.patch<RoutingRule>(`/routing/rules/${id}`, { enabled }),
  remove: (id) => http.delete<void>(`/routing/rules/${id}`),
}

export const routingService: RoutingService = USE_MOCKS
  ? mockRoutingService
  : httpRoutingService
