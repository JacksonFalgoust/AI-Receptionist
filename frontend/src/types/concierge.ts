import type { Id, IsoDateTime, TenantScoped } from './common'
import type { Channel } from './conversation'

/** PRD §6.2 — the persistent header badge. */
export type ConciergeState =
  | 'active'
  | 'paused'
  | 'setup_required'
  | 'maintenance'
  | 'connection_issue'

export interface ChannelStatus {
  channel: Channel
  enabled: boolean
  health: 'ok' | 'degraded' | 'down'
}

export interface ConnectedSystemSummary {
  id: Id
  name: string
  health: 'ok' | 'degraded' | 'down'
  lastSyncAt?: IsoDateTime
}

export interface ConciergeStatus {
  state: ConciergeState
  channels: ChannelStatus[]
  connectedSystems: ConnectedSystemSummary[]
  lastConfigurationChangeAt?: IsoDateTime
}

export interface BusinessHours {
  /** 0 = Sunday. */
  day: number
  open?: string
  close?: string
  closed: boolean
}

export interface BusinessProfile {
  name: string
  description: string
  phone: string
  website: string
  timezone: string
  address: string
  /** Free text (e.g. "3 locations") — PRD §13.1 asks for the field, not a per-location manager. */
  locations: string
  hours: BusinessHours[]
}

export type Tone = 'professional' | 'friendly' | 'casual' | 'formal' | 'custom'

export interface ConciergeIdentity {
  name: string
  greeting: string
  closing: string
  voice: string
  tone: Tone
  customTone?: string
  primaryLanguage: string
  supportedLanguages: string[]
}

/** PRD §13.3 — organizations rename domain nouns to match their business. */
export interface Terminology {
  customer: string
  reservation: string
  location: string
  employee: string
}

export interface ConciergeConfiguration extends TenantScoped {
  businessProfile: BusinessProfile
  identity: ConciergeIdentity
  terminology: Terminology
  /**
   * PRD §13.4: configuration is drafted, then explicitly published. A draft
   * must never reach production customers on save alone.
   */
  hasUnpublishedChanges: boolean
  lastPublishedAt?: IsoDateTime
}

/** PRD §14.2 */
export type FeatureStatus =
  | 'enabled'
  | 'disabled'
  | 'setup_required'
  | 'connection_required'
  | 'error'

export interface Feature {
  id: Id
  name: string
  description: string
  status: FeatureStatus
  requiredIntegrationId?: Id
  requiredIntegrationName?: string
  /** Disabling these prompts for confirmation (USER_STORIES US-7.1). */
  highImpact: boolean
}
