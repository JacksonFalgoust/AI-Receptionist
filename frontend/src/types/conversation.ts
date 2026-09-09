import type { Id, IsoDateTime, TenantScoped } from './common'

/**
 * PRD §9.1. The Conversations list may show `web`/`other`, even though the
 * Overview status card is Voice + SMS only per USER_STORIES US-2.3.
 */
export type Channel = 'voice' | 'sms' | 'web' | 'other'

export type ConversationOutcome =
  | 'completed'
  | 'escalated'
  | 'abandoned'
  | 'failed'
  | 'follow_up_required'

export interface Conversation extends TenantScoped {
  id: Id
  customerName?: string
  customerPhone?: string
  channel: Channel
  startedAt: IsoDateTime
  endedAt?: IsoDateTime
  durationSeconds?: number
  intent?: string
  outcome: ConversationOutcome
  escalated: boolean
  /** Business-language recap shown on the detail page (PRD §10.2). */
  summary?: string
  assignedEmployee?: string
  /**
   * The status of this conversation's escalation, when one exists. Joined on
   * by the service rather than stored — US-3.1's Status column asks "where
   * does this stand now", which Outcome ("how did it end") cannot answer.
   */
  escalationStatus?: EscalationStatus
}

export type Speaker = 'customer' | 'concierge' | 'employee'

export interface ConversationMessage {
  id: Id
  conversationId: Id
  speaker: Speaker
  text: string
  at: IsoDateTime
}

/**
 * PRD §10.4: one entry per system action Concierge performed, so an admin can
 * answer "what happened, which system, did it succeed".
 */
export interface ConversationAction {
  id: Id
  conversationId: Id
  action: string
  system: string
  at: IsoDateTime
  result: string
  status: 'success' | 'error' | 'pending'
  /** PRD §10.5 — expandable technical detail. Never contains credentials. */
  details?: Record<string, string>
}

/** The full record backing `/conversations/:id`. */
export interface ConversationDetail {
  conversation: Conversation
  messages: ConversationMessage[]
  actions: ConversationAction[]
}

export type EscalationStatus = 'new' | 'assigned' | 'in_progress' | 'resolved'

export interface Escalation extends TenantScoped {
  id: Id
  conversationId?: Id
  customerName: string
  reason: string
  assignedTo?: string
  status: EscalationStatus
  createdAt: IsoDateTime
}

/** Query shape for the Conversations list (PRD §9.2, §9.3). */
export interface ConversationFilters {
  search?: string
  channel?: Channel
  intent?: string
  outcome?: ConversationOutcome
  escalated?: boolean
  locationId?: Id
  assignedEmployee?: string
  from?: IsoDateTime
  to?: IsoDateTime
}

/** Option lists for the Conversations filter bar (US-3.1). */
export interface ConversationFilterOptions {
  intents: string[]
  locations: { id: Id; name: string }[]
  employees: string[]
}
