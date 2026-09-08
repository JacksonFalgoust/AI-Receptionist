import type { Id, IsoDateTime, TenantScoped } from './common'
import type { Channel } from './conversation'

/** A row in the Overview "Recent Activity" feed (USER_STORIES US-2.4). */
export interface ActivityEvent extends TenantScoped {
  id: Id
  at: IsoDateTime
  /** Business-language label, e.g. "Payment link sent". */
  title: string
  customerRef?: string
  channel?: Channel
  system?: string
  status: 'success' | 'error' | 'info' | 'escalated' | 'pending'
  conversationId?: Id
}

/** PRD §20.2 — Security & Audit is a post-MVP page; the model lands early. */
export interface AuditEvent extends TenantScoped {
  id: Id
  at: IsoDateTime
  /** Either a person's name or "GuideAnts Concierge" for system actions. */
  actor: string
  action: string
  category: string
  target?: string
  result: 'success' | 'failure'
}

export type NotificationKind =
  | 'integration_failure'
  | 'escalation'
  | 'workflow_error'
  | 'configuration_issue'
  | 'usage_limit'
  | 'security_event'

export interface Notification {
  id: Id
  kind: NotificationKind
  title: string
  body: string
  at: IsoDateTime
  read: boolean
  /** In-app route to open when the notification is clicked. */
  href?: string
}
