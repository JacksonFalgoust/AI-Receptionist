import type { Id, IsoDateTime } from './common'

/**
 * What `testConciergeService.simulate` produces for one exchange (US-13.1,
 * PRD §22.2). No `customerMessage` here — the caller already has it the
 * instant it's typed; a service that echoed its own input back would only
 * ever be asserting it copied a string correctly.
 *
 * `workflowUsed`/`knowledgeUsed`/`integrationsUsed`/`actionsExecuted` are all
 * optional and independent: PRD §22.2 shows them as per-exchange metadata,
 * not fields every reply has to fill in. A plain greeting has none of them.
 */
export interface TestConciergeReply {
  id: Id
  reply: string
  createdAt: IsoDateTime
  workflowUsed?: string
  knowledgeUsed?: string[]
  integrationsUsed?: string[]
  actionsExecuted?: string[]
}

/**
 * What `TestConciergePanel` renders: a reply paired with the message that
 * produced it. Assembled client-side in `TestConciergeDrawerContext`'s
 * `send()`, never returned by the service itself.
 */
export interface TestConciergeTurn extends TestConciergeReply {
  customerMessage: string
}
