import { cn } from '@/lib/cn'

export interface TimelineItem {
  id: string
  time: string
  title: string
  meta?: string
  tone?: 'default' | 'error'
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
        </li>
      ))}
    </ol>
  )
}
