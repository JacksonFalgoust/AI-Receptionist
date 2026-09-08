import { store } from '@/mocks/store'
import type { Id, Integration } from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

export interface ConnectIntegrationInput {
  /** Display label for the linked account, e.g. "ops@horizonpartners.example.com". */
  accountLabel: string
  /**
   * Sent once to establish the connection and never persisted. PRD §17.3 and
   * §47: a secret is never readable again once stored, so nothing keeps it here.
   */
  credentials?: Record<string, string>
}

/** PRD §17 / US-9.1. */
export interface IntegrationService {
  list(): Promise<Integration[]>
  connect(id: Id, input: ConnectIntegrationInput): Promise<Integration>
  repair(id: Id, input: ConnectIntegrationInput): Promise<Integration>
  disconnect(id: Id): Promise<Integration>
}

function requireIntegration(id: Id): Integration {
  const integration = store.integrations.find((item) => item.id === id)
  if (!integration) {
    throw new AppError({
      kind: 'not_found',
      title: 'Integration not found',
      description: 'That integration is not available for this organization.',
      actions: [{ label: 'Back to integrations', href: '/integrations' }],
    })
  }
  return integration
}

function markConnected(id: Id, accountLabel: string): Integration {
  const integration = requireIntegration(id)
  integration.status = 'connected'
  integration.connectedAccount = accountLabel
  integration.lastActivityAt = new Date().toISOString()
  // `credentials` is deliberately not touched — it is discarded with the argument.
  return integration
}

const mockIntegrationService: IntegrationService = {
  async list() {
    await delay()
    return [...store.integrations]
  },

  async connect(id, input) {
    await delay()
    return markConnected(id, input.accountLabel)
  },

  async repair(id, input) {
    await delay()
    return markConnected(id, input.accountLabel)
  },

  async disconnect(id) {
    await delay()
    const integration = requireIntegration(id)
    integration.status = 'not_connected'
    integration.connectedAccount = undefined
    return integration
  },
}

const httpIntegrationService: IntegrationService = {
  list: () => http.get<Integration[]>('/integrations'),
  connect: (id, input) => http.post<Integration>(`/integrations/${id}/connect`, input),
  repair: (id, input) => http.post<Integration>(`/integrations/${id}/repair`, input),
  disconnect: (id) => http.post<Integration>(`/integrations/${id}/disconnect`),
}

export const integrationService: IntegrationService = USE_MOCKS
  ? mockIntegrationService
  : httpIntegrationService
