import type {
  Channel,
  Conversation,
  ConversationAction,
  ConversationMessage,
  ConversationOutcome,
  Speaker,
} from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

/**
 * Horizon Partners, a professional-services firm (PRD §53.9 — industry
 * neutral). Timestamps are relative to module load so "Conversations Today" is
 * never zero when the demo is opened; service tests must assert on counts and
 * ordering, never on absolute dates.
 */

const NOW = Date.now()
const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

function isoAgo(msAgo: number): string {
  return new Date(NOW - msAgo).toISOString()
}

const CUSTOMERS = [
  { name: 'Alex Morgan', phone: '+1 555 0142' },
  { name: 'Dana Wu', phone: '+1 555 0178' },
  { name: 'Ibrahim Khan', phone: '+1 555 0119' },
  { name: 'Rosa Delgado', phone: '+1 555 0164' },
  { name: 'Nate Fischer', phone: '+1 555 0133' },
  { name: 'Yuki Tanaka', phone: '+1 555 0155' },
  { name: 'Marcus Bell', phone: '+1 555 0107' },
] as const

const CHANNELS: Channel[] = ['voice', 'sms', 'web', 'other']

const OUTCOMES: ConversationOutcome[] = [
  'completed',
  'escalated',
  'abandoned',
  'failed',
  'follow_up_required',
]

const INTENTS = [
  'Book appointment',
  'Reschedule appointment',
  'Cancel appointment',
  'Billing question',
  'Service status',
  'Update account details',
  'Request callback',
  'Pricing question',
] as const

const EMPLOYEES = ['Sam Rivera', 'Taylor Brooks', 'Priya Shah', 'Avery Chen'] as const

const LOCATIONS = ['loc_north', 'loc_riverside'] as const

const CONVERSATION_COUNT = 70

/**
 * Cycling the four unions by index guarantees every channel and every outcome
 * appears, so no Phase B rendering branch ships without a visible example.
 */
export const conversationSeed: Conversation[] = Array.from(
  { length: CONVERSATION_COUNT },
  (_, index) => {
    const customer = CUSTOMERS[index % CUSTOMERS.length]
    const channel = CHANNELS[index % CHANNELS.length]
    const outcome = OUTCOMES[index % OUTCOMES.length]
    const intent = INTENTS[index % INTENTS.length]
    const escalated = outcome === 'escalated'

    // The first 14 sit inside the last 24 hours; the rest spread back ~17 days.
    const startedMsAgo =
      index < 14 ? (index + 1) * 80 * MINUTE : DAY + (index - 13) * 7 * HOUR
    const durationSeconds = 45 + ((index * 37) % 540)

    return {
      id: `conv_${String(index + 1).padStart(4, '0')}`,
      organizationId: MOCK_ORGANIZATION_ID,
      locationId: LOCATIONS[index % LOCATIONS.length],
      customerName: customer.name,
      customerPhone: customer.phone,
      channel,
      startedAt: isoAgo(startedMsAgo),
      endedAt: isoAgo(startedMsAgo - durationSeconds * 1000),
      durationSeconds,
      intent,
      outcome,
      escalated,
      summary: `${customer.name} contacted Concierge about ${intent.toLowerCase()}. Concierge confirmed their details and ${
        escalated ? 'handed the request to a team member.' : 'completed the request on the call.'
      }`,
      assignedEmployee: escalated ? EMPLOYEES[index % EMPLOYEES.length] : undefined,
    }
  },
)

function buildMessages(conversation: Conversation): ConversationMessage[] {
  const startedMs = new Date(conversation.startedAt).getTime()
  const intent = conversation.intent?.toLowerCase() ?? 'my account'

  const script: { speaker: Speaker; text: string }[] = [
    { speaker: 'concierge', text: 'Thanks for contacting Horizon Partners. How can I help today?' },
    { speaker: 'customer', text: `Hi, I'm getting in touch about ${intent}.` },
    {
      speaker: 'concierge',
      text: 'Happy to help with that. Can I take your name and the best number to reach you?',
    },
    {
      speaker: 'customer',
      text: `${conversation.customerName}, and you can reach me on ${conversation.customerPhone}.`,
    },
  ]

  if (conversation.escalated) {
    script.push(
      { speaker: 'concierge', text: 'Let me bring in a colleague who can take this further.' },
      {
        speaker: 'employee',
        text: `This is ${conversation.assignedEmployee}. I can pick this up from here.`,
      },
    )
  } else {
    script.push({
      speaker: 'concierge',
      text: 'That is all confirmed. You will receive a written confirmation shortly.',
    })
  }

  return script.map((line, index) => ({
    id: `${conversation.id}_msg_${index + 1}`,
    conversationId: conversation.id,
    speaker: line.speaker,
    text: line.text,
    at: new Date(startedMs + index * 20_000).toISOString(),
  }))
}

type ActionTemplate = Omit<ConversationAction, 'id' | 'conversationId' | 'at'>

function buildActions(conversation: Conversation): ConversationAction[] {
  // PRD §10.5 / §47: `details` is expandable technical context for an admin and
  // must never carry credentials.
  const templates: ActionTemplate[] = [
    {
      action: 'Look up customer',
      system: 'Customer Records',
      result: `Matched ${conversation.customerName}`,
      status: 'success',
      details: { matchedOn: 'phone number', recordId: 'cust_00417' },
    },
  ]

  if (conversation.outcome === 'failed') {
    templates.push({
      action: 'Create appointment',
      system: 'Scheduling',
      result: 'Scheduling system did not respond',
      status: 'error',
      details: { attempts: '2', lastResponse: 'timed out after 30 seconds' },
    })
  } else if (conversation.outcome === 'completed') {
    templates.push(
      {
        action: 'Create appointment',
        system: 'Scheduling',
        result: 'Appointment confirmed',
        status: 'success',
        details: { reference: 'APT-4821', window: 'Thursday 10:00' },
      },
      {
        action: 'Send confirmation',
        system: 'Messaging',
        result: 'Message delivered',
        status: 'success',
        details: { channel: conversation.channel },
      },
    )
  } else if (conversation.escalated) {
    templates.push({
      action: 'Escalate to team',
      system: 'Escalation & Routing',
      result: `Assigned to ${conversation.assignedEmployee}`,
      status: 'success',
      details: { rule: 'Customer requests a person' },
    })
  } else {
    templates.push({
      action: 'Capture callback request',
      system: 'Customer Records',
      result: 'Callback requested',
      status: 'pending',
      details: { window: 'next business day' },
    })
  }

  const startedMs = new Date(conversation.startedAt).getTime()
  return templates.map((template, index) => ({
    ...template,
    id: `${conversation.id}_act_${index + 1}`,
    conversationId: conversation.id,
    at: new Date(startedMs + (index + 1) * 25_000).toISOString(),
  }))
}

export const conversationMessageSeed: ConversationMessage[] =
  conversationSeed.flatMap(buildMessages)

export const conversationActionSeed: ConversationAction[] =
  conversationSeed.flatMap(buildActions)
