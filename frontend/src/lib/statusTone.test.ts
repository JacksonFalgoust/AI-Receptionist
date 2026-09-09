import { describe, expect, it } from 'vitest'

import type { ActivityStatus } from '@/types/activity'
import type { ConciergeState, FeatureStatus } from '@/types/concierge'
import type { ConversationOutcome, EscalationStatus } from '@/types/conversation'
import type { IntegrationStatus } from '@/types/integration'
import type { KnowledgeStatus } from '@/types/knowledge'
import type { UserStatus } from '@/types/user'
import type { WorkflowStatus } from '@/types/workflow'

import { statusTone, TONE_CLASSES } from './statusTone'

const FEATURE_STATUSES: FeatureStatus[] = [
  'enabled',
  'disabled',
  'setup_required',
  'connection_required',
  'error',
]
const ESCALATION_STATUSES: EscalationStatus[] = ['new', 'assigned', 'in_progress', 'resolved']
const INTEGRATION_STATUSES: IntegrationStatus[] = [
  'connected',
  'not_connected',
  'setup_required',
  'connection_error',
  'authentication_expired',
]
const USER_STATUSES: UserStatus[] = ['active', 'invited', 'disabled']
const KNOWLEDGE_STATUSES: KnowledgeStatus[] = [
  'active',
  'processing',
  'needs_review',
  'error',
  'disabled',
]
const WORKFLOW_STATUSES: WorkflowStatus[] = ['draft', 'active', 'inactive']
const CONCIERGE_STATES: ConciergeState[] = [
  'active',
  'paused',
  'setup_required',
  'maintenance',
  'connection_issue',
]
const CHANNEL_HEALTHS = ['ok', 'degraded', 'down'] as const
const ACTIVITY_STATUSES: ActivityStatus[] = ['success', 'error', 'info', 'escalated', 'pending']
const CONVERSATION_OUTCOMES: ConversationOutcome[] = [
  'completed',
  'escalated',
  'abandoned',
  'failed',
  'follow_up_required',
]

const ALL_STATUSES = [
  ...FEATURE_STATUSES,
  ...ESCALATION_STATUSES,
  ...INTEGRATION_STATUSES,
  ...USER_STATUSES,
  ...KNOWLEDGE_STATUSES,
  ...WORKFLOW_STATUSES,
  ...CONCIERGE_STATES,
  ...CHANNEL_HEALTHS,
  ...ACTIVITY_STATUSES,
  ...CONVERSATION_OUTCOMES,
]

describe('statusTone', () => {
  it.each(ALL_STATUSES)('maps %s to a known tone and a non-empty label', (status) => {
    const result = statusTone(status)
    expect(['success', 'warning', 'danger', 'info', 'muted']).toContain(result.tone)
    expect(result.label.length).toBeGreaterThan(0)
  })

  it('gives every status its own human-readable label, not the raw enum value', () => {
    expect(statusTone('setup_required').label).toBe('Setup required')
    expect(statusTone('in_progress').label).toBe('In progress')
    expect(statusTone('not_connected').label).toBe('Not connected')
  })

  it('labels an activity outcome as the outcome, not as a workflow state', () => {
    expect(statusTone('success')).toEqual({ tone: 'success', label: 'Success' })
    expect(statusTone('escalated')).toEqual({ tone: 'danger', label: 'Escalated' })
    expect(statusTone('pending')).toEqual({ tone: 'warning', label: 'Pending' })
    expect(statusTone('info')).toEqual({ tone: 'info', label: 'Info' })
  })

  it('labels a conversation outcome as how the call ended', () => {
    expect(statusTone('completed')).toEqual({ tone: 'success', label: 'Completed' })
    expect(statusTone('abandoned')).toEqual({ tone: 'muted', label: 'Abandoned' })
    expect(statusTone('failed')).toEqual({ tone: 'danger', label: 'Failed' })
    expect(statusTone('follow_up_required')).toEqual({
      tone: 'warning',
      label: 'Follow-up required',
    })
  })

  it('exposes a Tailwind class string for every tone', () => {
    for (const tone of ['success', 'warning', 'danger', 'info', 'muted'] as const) {
      expect(TONE_CLASSES[tone].length).toBeGreaterThan(0)
    }
  })
})
