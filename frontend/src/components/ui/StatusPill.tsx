import { statusTone, TONE_CLASSES } from '@/lib/statusTone'
import type { KnownStatus } from '@/lib/statusTone'
import { cn } from '@/lib/cn'

export interface StatusPillProps {
  status: KnownStatus
}

export function StatusPill({ status }: StatusPillProps) {
  const { tone, label } = statusTone(status)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold',
        TONE_CLASSES[tone],
      )}
    >
      {label}
    </span>
  )
}
