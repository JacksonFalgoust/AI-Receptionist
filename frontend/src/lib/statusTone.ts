import type { ActivityStatus } from '@/types/activity'
import type { ConciergeState, FeatureStatus } from '@/types/concierge'
import type { ConversationOutcome, EscalationStatus } from '@/types/conversation'
import type { IntegrationStatus } from '@/types/integration'
import type { KnowledgeStatus } from '@/types/knowledge'
import type { UserStatus } from '@/types/user'
import type { WorkflowStatus } from '@/types/workflow'
import type { BillingStatus, InvoiceStatus } from '@/types/billing'

/**
 * Semantic UI tone, separate from `types/concierge.Tone` (the Concierge's voice/persona setting).
 * This represents how a status should visually appear: success, warning, danger, info, or muted.
 */
export type SemanticTone = 'success' | 'warning' | 'danger' | 'info' | 'muted'

export interface ToneInfo {
  tone: SemanticTone
  label: string
}

/** `ChannelStatus['health']` / `ConnectedSystemSummary['health']` aren't exported as a named type. */
type ChannelHealth = 'ok' | 'degraded' | 'down'

/**
 * Every status-like literal in the domain model. `Record<KnownStatus, ToneInfo>`
 * below forces every member of every constituent union to have an entry —
 * adding a new status value to any of these types is a compile error here
 * until it's given a tone and a label.
 */
export type KnownStatus =
  | FeatureStatus
  | EscalationStatus
  | IntegrationStatus
  | UserStatus
  | KnowledgeStatus
  | WorkflowStatus
  | ConciergeState
  | ChannelHealth
  | ActivityStatus
  | ConversationOutcome
  | BillingStatus
  | InvoiceStatus

const STATUS_TONE: Record<KnownStatus, ToneInfo> = {
  enabled: { tone: 'success', label: 'Enabled' },
  disabled: { tone: 'muted', label: 'Disabled' },
  setup_required: { tone: 'warning', label: 'Setup required' },
  connection_required: { tone: 'warning', label: 'Connection required' },
  error: { tone: 'danger', label: 'Error' },
  new: { tone: 'info', label: 'New' },
  assigned: { tone: 'info', label: 'Assigned' },
  in_progress: { tone: 'warning', label: 'In progress' },
  resolved: { tone: 'success', label: 'Resolved' },
  connected: { tone: 'success', label: 'Connected' },
  not_connected: { tone: 'muted', label: 'Not connected' },
  connection_error: { tone: 'danger', label: 'Connection error' },
  authentication_expired: { tone: 'danger', label: 'Authentication expired' },
  active: { tone: 'success', label: 'Active' },
  invited: { tone: 'info', label: 'Invited' },
  processing: { tone: 'info', label: 'Processing' },
  needs_review: { tone: 'warning', label: 'Needs review' },
  draft: { tone: 'muted', label: 'Draft' },
  inactive: { tone: 'muted', label: 'Inactive' },
  paused: { tone: 'warning', label: 'Paused' },
  maintenance: { tone: 'warning', label: 'Maintenance' },
  connection_issue: { tone: 'danger', label: 'Connection issue' },
  ok: { tone: 'success', label: 'Operational' },
  degraded: { tone: 'warning', label: 'Degraded' },
  down: { tone: 'danger', label: 'Down' },
  // ActivityStatus. 'error' is shared with FeatureStatus/KnowledgeStatus above.
  success: { tone: 'success', label: 'Success' },
  info: { tone: 'info', label: 'Info' },
  escalated: { tone: 'danger', label: 'Escalated' },
  pending: { tone: 'warning', label: 'Pending' },
  // ConversationOutcome. 'escalated' is shared with ActivityStatus above.
  completed: { tone: 'success', label: 'Completed' },
  abandoned: { tone: 'muted', label: 'Abandoned' },
  failed: { tone: 'danger', label: 'Failed' },
  follow_up_required: { tone: 'warning', label: 'Follow-up required' },
  // BillingStatus. 'active' is shared with UserStatus/ConciergeState above.
  past_due: { tone: 'danger', label: 'Past due' },
  trialing: { tone: 'info', label: 'Trial' },
  canceled: { tone: 'muted', label: 'Canceled' },
  // InvoiceStatus.
  paid: { tone: 'success', label: 'Paid' },
  due: { tone: 'warning', label: 'Due' },
  overdue: { tone: 'danger', label: 'Overdue' },
}

export function statusTone(status: KnownStatus): ToneInfo {
  return STATUS_TONE[status]
}

/** Shared background/text classes for a semantic tone — pills, badges, alerts, toasts. */
export const TONE_CLASSES: Record<SemanticTone, string> = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  info: 'bg-info-soft text-info',
  muted: 'bg-canvas-tint text-ink-muted',
}
