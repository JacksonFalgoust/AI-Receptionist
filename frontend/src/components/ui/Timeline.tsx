import type { ReactNode } from 'react'

import { cn } from '@/lib/cn'

export interface TimelineItem {
  id: string
  time: string
  title: string
  meta?: string
  tone?: 'default' | 'error'
  /**
   * Optional technical context, hidden until asked for (US-3.2, PRD §10.5).
   * A native `<details>` rather than a hand-rolled disclosure: it is keyboard
   * operable and correctly announced without any state of our own.
   */
  details?: ReactNode
}

export interface TimelineProps {
  items: TimelineItem[]
}

export function Timeline({ items }: TimelineProps) {
  return (
    <ol className="relative space-y-4 border-l border-border pl-4">
      {items.map((item) => (
        <li key={item.id} className="relative">
          <span
            className={cn(
              'absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full',
              item.tone === 'error' ? 'bg-danger' : 'bg-brand',
            )}
            aria-hidden
          />
          <p className="text-xs text-ink-muted">{item.time}</p>
          <p className="text-sm font-medium text-ink">{item.title}</p>
          {item.meta ? <p className="text-xs text-ink-secondary">{item.meta}</p> : null}
          {item.details ? (
            <details className="mt-1">
              <summary className="cursor-pointer text-xs font-semibold text-ink-secondary hover:text-ink">
                System details
              </summary>
              <div className="mt-1">{item.details}</div>
            </details>
          ) : null}
        </li>
      ))}
    </ol>
  )
}
