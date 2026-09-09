import { ChatBubble } from '@/components/ui/ChatBubble'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatDateTime } from '@/lib/formatDate'
import type { ConversationMessage } from '@/types'

export interface ConversationTranscriptProps {
  /** Oldest first — the service sorts, a transcript reads forwards. */
  messages: ConversationMessage[]
}

/**
 * US-3.2: the interaction as it happened, with Customer, Concierge and
 * Employee turns distinguished. `ChatBubble` supplies the speaker label, so
 * a speaker is never identified by bubble colour alone.
 */
export function ConversationTranscript({ messages }: ConversationTranscriptProps) {
  if (messages.length === 0) {
    return (
      <EmptyState
        title="No transcript for this conversation"
        description="Nothing was captured for this interaction."
      />
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {messages.map((message) => (
        <ChatBubble
          key={message.id}
          speaker={message.speaker}
          message={message.text}
          time={formatDateTime(message.at)}
        />
      ))}
    </div>
  )
}
