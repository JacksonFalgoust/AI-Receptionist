import type { ReactNode } from 'react'

import { StatusPill } from '@/components/ui/StatusPill'
import { CHANNEL_LABELS } from '@/lib/channelLabels'
import { formatDateTime, formatDuration } from '@/lib/formatDate'
import type { Conversation } from '@/types'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-semibold text-ink-muted">{label}</span>
      <span className="text-sm text-ink">{children}</span>
    </div>
  )
}

export interface ConversationSummaryStripProps {
  conversation: Conversation
}

/**
 * US-3.2's summary block. The customer is the page title, so this carries the
 * remaining six facts — the ones that answer "what was this call" before
 * anyone reads a word of the transcript.
 */
export function ConversationSummaryStrip({ conversation }: ConversationSummaryStripProps) {
  return (
    <div className="grid grid-cols-2 gap-4 rounded-lg border border-border bg-surface p-4 md:grid-cols-3 xl:grid-cols-6">
      <Fact label="Channel">{CHANNEL_LABELS[conversation.channel]}</Fact>
      <Fact label="Started">{formatDateTime(conversation.startedAt)}</Fact>
      <Fact label="Duration">{formatDuration(conversation.durationSeconds)}</Fact>
      <Fact label="Intent">{conversation.intent ?? '—'}</Fact>
      <Fact label="Outcome">
        <StatusPill status={conversation.outcome} />
      </Fact>
      <Fact label="Escalation">
        {/*
          "Not escalated" rather than a blank cell: the absence of an escalation
          is an answer to the question, not missing data.
        */}
        {conversation.escalationStatus ? (
          <StatusPill status={conversation.escalationStatus} />
        ) : (
          <span className="text-ink-secondary">Not escalated</span>
        )}
      </Fact>
    </div>
  )
}
