import { cn } from '@/lib/cn'

export type ChatSpeaker = 'customer' | 'concierge' | 'employee'

export interface ChatBubbleProps {
  speaker: ChatSpeaker
  message: string
  time?: string
}

const SPEAKER_LABEL: Record<ChatSpeaker, string> = {
  customer: 'Customer',
  concierge: 'Concierge',
  employee: 'Employee',
}

const SPEAKER_CLASSES: Record<ChatSpeaker, string> = {
  customer: 'self-start bg-canvas-tint text-ink',
  concierge: 'self-end bg-brand-soft text-brand-ink',
  employee: 'self-end bg-info-soft text-info',
}

export function ChatBubble({ speaker, message, time }: ChatBubbleProps) {
  return (
    <div
      className={cn(
        'flex max-w-[75%] flex-col gap-0.5 rounded-lg px-3 py-2 text-sm',
        SPEAKER_CLASSES[speaker],
      )}
    >
      <span className="text-xs font-semibold">{SPEAKER_LABEL[speaker]}</span>
      <span>{message}</span>
      {time ? <span className="text-xs text-ink-muted">{time}</span> : null}
    </div>
  )
}
