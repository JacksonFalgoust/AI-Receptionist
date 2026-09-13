import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/cn'

export interface PanelProps extends HTMLAttributes<HTMLDivElement> {}

export function Panel({ className, children, ...props }: PanelProps) {
  return (
    <div
      className={cn('rounded-lg border border-border bg-surface shadow-sm', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export interface PanelHeaderProps {
  title: string
  action?: ReactNode
}

export function PanelHeader({ title, action }: PanelHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {action}
    </div>
  )
}
