import type { IntegrationStatus } from '@/types'

/** Which `integrationService` call an action resolves to. */
export type IntegrationActionKind = 'connect' | 'repair'

export interface IntegrationAction {
  /** Card button label and modal CTA — one label, so the two can never drift. */
  label: string
  kind: IntegrationActionKind
  /** Modal intro copy: what this action is for, in business language. */
  intro: string
}

/**
 * US-9.1's Connect / Continue setup / Repair, keyed by the status that calls
 * for them. `null` means the connection is working and there is nothing to do
 * — no "update credentials", which neither PRD §17 nor US-9.1 asks for and
 * which no user could see the effect of.
 */
export const INTEGRATION_ACTION: Record<IntegrationStatus, IntegrationAction | null> = {
  not_connected: {
    label: 'Connect',
    kind: 'connect',
    intro: 'Enter the details Concierge should use to reach this system.',
  },
  setup_required: {
    label: 'Continue setup',
    kind: 'connect',
    intro: 'This connection was started but never finished. Enter the remaining details to complete it.',
  },
  connection_error: {
    label: 'Repair connection',
    kind: 'repair',
    intro: 'Concierge could not reach this system. Re-enter the connection details to restore it.',
  },
  authentication_expired: {
    label: 'Reconnect',
    kind: 'repair',
    intro: 'Access to this system has expired. Enter current details to reconnect it.',
  },
  connected: null,
}

export function integrationAction(status: IntegrationStatus): IntegrationAction | null {
  return INTEGRATION_ACTION[status]
}

/**
 * Disconnect is offered for anything that has been started — including a
 * half-finished setup or a broken connection, so a stuck one can be abandoned.
 * `disconnect()` resets the status to `not_connected`, which is why that one
 * status has nothing to disconnect from.
 */
export function canDisconnect(status: IntegrationStatus): boolean {
  return status !== 'not_connected'
}
