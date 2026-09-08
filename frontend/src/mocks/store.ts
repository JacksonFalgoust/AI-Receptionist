import type {
  Conversation,
  ConversationAction,
  ConversationMessage,
  Organization,
} from '@/types'

import {
  conversationActionSeed,
  conversationMessageSeed,
  conversationSeed,
} from './conversations'
import { organizationSeed } from './organizations'
import { resetIds } from './query'

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
}

function seed(): MockStore {
  return {
    organizations: structuredClone(organizationSeed),
    conversations: structuredClone(conversationSeed),
    conversationMessages: structuredClone(conversationMessageSeed),
    conversationActions: structuredClone(conversationActionSeed),
  }
}

export const store: MockStore = seed()

/** Restores pristine data and id sequencing. Call in `beforeEach`. */
export function resetStore(): void {
  Object.assign(store, seed())
  resetIds()
}
