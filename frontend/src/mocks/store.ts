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

/** Restores pristine data and id sequencing. Call in `beforeEach`. */
export function resetStore(): void {
  Object.assign(store, seed())
  resetIds()
  // Compute max ID from all seeded arrays to avoid collisions
  const allIds = Object.values(store)
    .flatMap((arr) => (Array.isArray(arr) ? arr : []))
    .filter((item) => typeof item === 'object' && item !== null && 'id' in item)
    .map((item) => {
      const id = (item as any).id
      const match = id.match(/_(\d+)$/)
      return match ? parseInt(match[1], 10) : 0
    })
  const maxId = Math.max(...allIds, 0)
  if (maxId > 0) {
    initializeIdCounter(maxId)
  }
}
