import { nextId } from '@/mocks/query'
import type { TestConciergeReply } from '@/types'

import { delay, USE_MOCKS } from './config'
import { http } from './http'

export interface TestConciergeService {
  simulate(message: string): Promise<TestConciergeReply>
}

interface CannedReply {
  keywords: string[]
  reply: string
  workflowUsed?: string
  knowledgeUsed?: string[]
  integrationsUsed?: string[]
  actionsExecuted?: string[]
}

/**
 * Ordered, first match wins. Named after real seeded records
 * (`mocks/workflows.ts`, `mocks/knowledge.ts`, `mocks/integrations.ts`) so a
 * reply about "booking" plausibly cites the same "Book an appointment"
 * workflow the rest of the app already shows — this is E3's mocked text
 * simulation, not a live GuideAnts call (that contract is E6).
 */
const CANNED_REPLIES: CannedReply[] = [
  {
    keywords: ['hour', 'open'],
    reply:
      'We are open Monday to Thursday 8:30am–5:30pm and Friday 8:30am–4:00pm, closed weekends.',
    knowledgeUsed: ['What are your opening hours?'],
  },
  {
    keywords: ['cancel', 'reschedul'],
    reply:
      'Call or text us at least 24 hours ahead and we will move your appointment to the next available time.',
    workflowUsed: 'Reschedule an appointment',
    knowledgeUsed: ['How do I reschedule an appointment?'],
    integrationsUsed: ['Scheduling'],
  },
  {
    keywords: ['book', 'appointment', 'schedule'],
    reply: "I can help with that. Let's find a time that works for you.",
    workflowUsed: 'Book an appointment',
    integrationsUsed: ['Scheduling'],
    actionsExecuted: ['Checked availability', 'Created a hold'],
  },
  {
    keywords: ['pay', 'bill', 'invoice'],
    reply:
      'We accept all major cards and bank transfer. I can send a payment link to your phone or email.',
    workflowUsed: 'Send a payment link',
    knowledgeUsed: ['What payment methods do you accept?'],
    integrationsUsed: ['Payments'],
    actionsExecuted: ['Sent a payment link'],
  },
  {
    keywords: ['complain', 'upset', 'problem', 'unhappy'],
    reply:
      "I'm sorry to hear that. I've flagged this for a team member to follow up with you directly.",
    workflowUsed: 'Handle a complaint',
    integrationsUsed: ['Customer Records'],
    actionsExecuted: ['Flagged for human follow-up'],
  },
]

const FALLBACK_REPLY =
  'I can help with scheduling, billing, and general questions. Could you tell me a bit more about what you need?'

function findCannedReply(message: string): CannedReply | undefined {
  const lower = message.toLowerCase()
  return CANNED_REPLIES.find((candidate) =>
    candidate.keywords.some((keyword) => lower.includes(keyword)),
  )
}

const mockTestConciergeService: TestConciergeService = {
  async simulate(message) {
    await delay()
    const canned = findCannedReply(message)
    return {
      id: nextId('tc'),
      createdAt: new Date().toISOString(),
      reply: canned?.reply ?? FALLBACK_REPLY,
      workflowUsed: canned?.workflowUsed,
      knowledgeUsed: canned?.knowledgeUsed,
      integrationsUsed: canned?.integrationsUsed,
      actionsExecuted: canned?.actionsExecuted,
    }
  },
}

/** Unused while `USE_MOCKS` is true. E6 defines this contract for real. */
const httpTestConciergeService: TestConciergeService = {
  simulate: (message) => http.post<TestConciergeReply>('/concierge/test', { message }),
}

export const testConciergeService: TestConciergeService = USE_MOCKS
  ? mockTestConciergeService
  : httpTestConciergeService
