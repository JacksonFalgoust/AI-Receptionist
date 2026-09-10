import { useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import { cn } from '@/lib/cn'

export interface TabItem {
  value: string
  label: string
  /** Flags a validation error inside this tab's content — visible even while another tab is active. */
  hasError?: boolean
}

export interface TabsProps {
  items: TabItem[]
  value: string
  onChange: (value: string) => void
  children: ReactNode
}

export function Tabs({ items, value, onChange, children }: TabsProps) {
  // Scope DOM ids per instance so two Tabs on one page with overlapping item values never collide
  const instanceId = useId()
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const focusAndSelect = (nextValue: string) => {
    onChange(nextValue)
    tabRefs.current[nextValue]?.focus()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = items.findIndex((item) => item.value === value)
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      focusAndSelect(items[(index + 1) % items.length].value)
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault()
      focusAndSelect(items[(index - 1 + items.length) % items.length].value)
    } else if (event.key === 'Home') {
      event.preventDefault()
      focusAndSelect(items[0].value)
    } else if (event.key === 'End') {
      event.preventDefault()
      focusAndSelect(items[items.length - 1].value)
    }
  }

  return (
    <div>
      <div
        role="tablist"
        aria-orientation="horizontal"
        onKeyDown={handleKeyDown}
        className="flex gap-1 border-b border-border"
      >
        {items.map((item) => {
          const isActive = item.value === value
          return (
            <button
              key={item.value}
              ref={(el) => {
                tabRefs.current[item.value] = el
              }}
              role="tab"
              type="button"
              id={`${instanceId}-tab-${item.value}`}
              aria-selected={isActive}
              aria-controls={`${instanceId}-panel-${item.value}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => onChange(item.value)}
              className={cn(
                'px-3 py-2 text-sm font-medium',
                isActive ? 'border-b-2 border-brand text-brand-ink' : 'text-ink-secondary',
              )}
            >
              {item.label}
              {item.hasError ? (
                <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-danger align-middle">
                  <span className="sr-only"> (has an error)</span>
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={`${instanceId}-panel-${value}`} aria-labelledby={`${instanceId}-tab-${value}`} className="pt-3">
        {children}
      </div>
    </div>
  )
}
