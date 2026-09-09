import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { Conversation, ConversationAction, ConversationMessage } from '@/types'

import { ConversationActionTimeline } from './ConversationActionTimeline'
import { ConversationSummaryStrip } from './ConversationSummaryStrip'
import { ConversationTranscript } from './ConversationTranscript'

const conversation: Conversation = {
  id: 'conv_0002',
  organizationId: 'org_horizon',
  customerName: 'Dana Wu',
  channel: 'voice',
  startedAt: '2026-09-08T18:27:00.000Z',
  durationSeconds: 252,
  intent: 'Refund question',
  outcome: 'escalated',
  escalated: true,
  escalationStatus: 'in_progress',
}

describe('ConversationSummaryStrip', () => {
  it('reports the six facts US-3.2 asks for beside the customer', () => {
    render(<ConversationSummaryStrip conversation={conversation} />)

    expect(screen.getByText('Channel').closest('div')).toHaveTextContent('Voice')
    expect(screen.getByText('Duration').closest('div')).toHaveTextContent('4m 12s')
    expect(screen.getByText('Intent').closest('div')).toHaveTextContent('Refund question')
    expect(screen.getByText('Outcome').closest('div')).toHaveTextContent('Escalated')
    expect(screen.getByText('Escalation').closest('div')).toHaveTextContent('In progress')
    expect(screen.getByText('Started')).toBeInTheDocument()
  })

  it('says an escalation is absent rather than leaving the field blank', () => {
    render(
      <ConversationSummaryStrip
        conversation={{ ...conversation, escalated: false, escalationStatus: undefined }}
      />,
    )

    expect(screen.getByText('Escalation').closest('div')).toHaveTextContent('Not escalated')
  })

  it('falls back where a conversation never captured an intent or duration', () => {
    render(
      <ConversationSummaryStrip
        conversation={{ ...conversation, intent: undefined, durationSeconds: undefined }}
      />,
    )

    expect(screen.getByText('Intent').closest('div')).toHaveTextContent('—')
    expect(screen.getByText('Duration').closest('div')).toHaveTextContent('—')
  })
})

const messages: ConversationMessage[] = [
  { id: 'm1', conversationId: 'conv_0002', speaker: 'concierge', text: 'How can I help?', at: '2026-09-08T18:27:05.000Z' },
  { id: 'm2', conversationId: 'conv_0002', speaker: 'customer', text: 'I need a refund.', at: '2026-09-08T18:27:14.000Z' },
  { id: 'm3', conversationId: 'conv_0002', speaker: 'employee', text: 'This is Sam, taking over.', at: '2026-09-08T18:31:02.000Z' },
]

describe('ConversationTranscript', () => {
  it('labels all three speakers US-3.2 names', () => {
    render(<ConversationTranscript messages={messages} />)

    expect(screen.getByText('Customer')).toBeInTheDocument()
    expect(screen.getByText('Concierge')).toBeInTheDocument()
    expect(screen.getByText('Employee')).toBeInTheDocument()
    expect(screen.getByText('I need a refund.')).toBeInTheDocument()
  })

  it('says so when a conversation has no transcript', () => {
    render(<ConversationTranscript messages={[]} />)

    expect(screen.getByText('No transcript for this conversation')).toBeInTheDocument()
  })
})

const actions: ConversationAction[] = [
  {
    id: 'a1',
    conversationId: 'conv_0002',
    action: 'Look up customer',
    system: 'Customer Records',
    at: '2026-09-08T18:27:10.000Z',
    result: 'Matched Dana Wu',
    status: 'success',
    details: { matchedOn: 'phone number', recordId: 'cust_00417' },
  },
  {
    id: 'a2',
    conversationId: 'conv_0002',
    action: 'Create appointment',
    system: 'Scheduling',
    at: '2026-09-08T18:28:02.000Z',
    result: 'Scheduling system did not respond',
    status: 'error',
  },
]

describe('ConversationActionTimeline', () => {
  it('reports the action, the system, and the result for each entry', () => {
    render(<ConversationActionTimeline actions={actions} />)

    const entry = screen.getByText('Look up customer').closest('li')!
    expect(entry).toHaveTextContent('Customer Records')
    expect(entry).toHaveTextContent('Matched Dana Wu')
  })

  it('marks a failed action so it is distinguishable from a successful one', () => {
    render(<ConversationActionTimeline actions={actions} />)

    const failed = screen.getByText('Create appointment').closest('li')!
    const succeeded = screen.getByText('Look up customer').closest('li')!
    expect(failed.querySelector('span')).toHaveClass('bg-danger')
    expect(succeeded.querySelector('span')).toHaveClass('bg-brand')
  })

  it('hides system details until an administrator asks for them', async () => {
    const user = userEvent.setup()
    render(<ConversationActionTimeline actions={actions} />)

    const entry = screen.getByText('Look up customer').closest('li')!
    const disclosure = within(entry).getByRole('group')
    expect(disclosure).not.toHaveAttribute('open')

    await user.click(within(disclosure).getByText('System details'))

    expect(disclosure).toHaveAttribute('open')
    expect(within(entry).getByText('matchedOn')).toBeInTheDocument()
    expect(within(entry).getByText('phone number')).toBeInTheDocument()
  })

  it('offers no disclosure for an action that recorded no details', () => {
    render(<ConversationActionTimeline actions={actions} />)

    const entry = screen.getByText('Create appointment').closest('li')!
    expect(within(entry).queryByRole('group')).not.toBeInTheDocument()
  })

  it('says so when Concierge took no system actions', () => {
    render(<ConversationActionTimeline actions={[]} />)

    expect(screen.getByText('No system actions were taken')).toBeInTheDocument()
  })
})
