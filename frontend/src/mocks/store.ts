import type {
  ActivityEvent,
  BillingOverview,
  ConciergeConfiguration,
  ConciergeStatus,
  Conversation,
  ConversationAction,
  ConversationMessage,
  Escalation,
  Feature,
  Integration,
  KnowledgeItem,
  Notification,
  Organization,
  RoutingRule,
  User,
  Workflow,
} from '@/types'

import { activityEventSeed, escalationSeed } from './activity'
import { billingOverviewSeed } from './billing'
import {
  conciergeConfigurationSeed,
  conciergeStatusSeed,
  featureSeed,
} from './concierge'
import {
  conversationActionSeed,
  conversationMessageSeed,
  conversationSeed,
} from './conversations'
import { integrationSeed } from './integrations'
import { knowledgeSeed } from './knowledge'
import { notificationSeed } from './notifications'
import { organizationSeed } from './organizations'
import { initializeIdCounter, resetIds } from './query'
import { routingRuleSeed } from './routing'
import { userSeed } from './users'
import { workflowSeed } from './workflows'

/**
 * The mutable side of the mock layer. Fixtures stay pure data; this clones them
 * once at import so mock writes are visible on later reads and a save →
 * navigate away → come back round-trip works within a session.
 *
 * In-memory by design: a refresh restores the pristine demo data, and tests get
 * a deterministic starting state from `resetStore()`.
 *
 * PRD §38: only files under `src/services/` may import this module.
 *
 * Mock reads return references into these live arrays/objects, not copies.
 * A caller must never mutate a value returned from a service directly —
 * only the corresponding service method may change store state. Some
 * service mutators (e.g. conciergeService.pause/resume) mutate the
 * existing object in place; others (e.g. conciergeService.saveDraft/publish,
 * workflowService.saveDraft/publish) replace it via reassignment. Both are
 * safe from a caller's perspective — the return value always reflects
 * current state — but this means a cached result (e.g. in React Query)
 * CAN be silently rewritten by an unrelated in-place mutation elsewhere.
 *
 * The HTTP service implementations always return freshly-parsed JSON, with
 * no such aliasing. A component that relies on reference identity of a
 * mock-returned value will behave differently once VITE_USE_MOCKS=false.
 * Treat this as a known, accepted trade-off for the mock layer, not a
 * pattern to build on deliberately — Phase B+ work should not rely on
 * mock-read aliasing for correctness.
 */
export interface MockStore {
  organizations: Organization[]
  conversations: Conversation[]
  conversationMessages: ConversationMessage[]
  conversationActions: ConversationAction[]
  activityEvents: ActivityEvent[]
  escalations: Escalation[]
  notifications: Notification[]
  conciergeStatus: ConciergeStatus
  conciergeConfiguration: ConciergeConfiguration
  features: Feature[]
  workflows: Workflow[]
  knowledge: KnowledgeItem[]
  integrations: Integration[]
  routingRules: RoutingRule[]
  users: User[]
  billing: BillingOverview
}

function seed(): MockStore {
  return {
    organizations: structuredClone(organizationSeed),
    conversations: structuredClone(conversationSeed),
    conversationMessages: structuredClone(conversationMessageSeed),
    conversationActions: structuredClone(conversationActionSeed),
    activityEvents: structuredClone(activityEventSeed),
    escalations: structuredClone(escalationSeed),
    notifications: structuredClone(notificationSeed),
    conciergeStatus: structuredClone(conciergeStatusSeed),
    conciergeConfiguration: structuredClone(conciergeConfigurationSeed),
    features: structuredClone(featureSeed),
    workflows: structuredClone(workflowSeed),
    knowledge: structuredClone(knowledgeSeed),
    integrations: structuredClone(integrationSeed),
    routingRules: structuredClone(routingRuleSeed),
    users: structuredClone(userSeed),
    billing: structuredClone(billingOverviewSeed),
  }
}

export const store: MockStore = seed()
syncIdCounter()

/**
 * Scans every seeded array for the highest numeric suffix on an `id` field
 * (e.g. `kn_0001` -> 1) and advances the shared id counter past it, so the
 * next `nextId('kn')`/`nextId('rr')` call can never collide with a seeded
 * record. Must run once at module load (so the running app's first created
 * record is safe) and again from `resetStore()` (so tests get the same
 * guarantee after each reset).
 */
function syncIdCounter(): void {
  const allIds = Object.values(store)
    .flatMap((arr) => (Array.isArray(arr) ? arr : []))
    .filter((item) => typeof item === 'object' && item !== null && 'id' in item)
    .map((item) => {
      const id = (item as { id?: unknown }).id
      if (typeof id !== 'string') return 0
      const match = id.match(/_(\d+)$/)
      return match ? parseInt(match[1], 10) : 0
    })
  const maxId = Math.max(...allIds, 0)
  if (maxId > 0) {
    initializeIdCounter(maxId)
  }
}

/** Restores pristine data and id sequencing. Call in `beforeEach`. */
export function resetStore(): void {
  Object.assign(store, seed())
  resetIds()
  syncIdCounter()
}
