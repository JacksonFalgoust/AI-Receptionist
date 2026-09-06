import type { ReactNode } from 'react'

import { cn } from '@/lib/cn'
import { TONE_CLASSES } from '@/lib/statusTone'
import type { SemanticTone } from '@/lib/statusTone'

export interface BadgeProps {
  tone?: SemanticTone
  children: ReactNode
}

export function Badge({ tone = 'muted', children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
        TONE_CLASSES[tone],
      )}
    >
      {children}
    </span>
  )
}
