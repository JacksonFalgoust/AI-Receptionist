import { useId } from 'react'

import { cn } from '@/lib/cn'
import type { DateRangePreset } from '@/types'

/**
 * `DateRangePreset` also has `custom`, which needs a date picker and ships no
 * UI in the MVP. Listing the three here rather than deriving from the type
 * keeps that omission deliberate and ordered shortest-window-first.
 */
const PRESETS: { value: DateRangePreset; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
]

export interface DateScopeProps {
  value: DateRangePreset
  onChange: (preset: DateRangePreset) => void
}

/**
 * US-2.1: the date scope control in the Overview page header.
 *
 * Built on real radio inputs rather than buttons with `role="radio"`. The
 * browser then supplies arrow-key navigation, the single tab stop, and the
 * checked semantics for free — all of which a hand-rolled roving-tabindex
 * group gets wrong sooner or later. The inputs are visually hidden, not
 * `display: none`, so they stay focusable and announceable.
 */
export function DateScope({ value, onChange }: DateScopeProps) {
  // Two Overviews on one page would otherwise share a radio name and fight.
  const name = useId()

  return (
    <div
      role="radiogroup"
      aria-label="Date scope"
      className="inline-flex rounded-md border border-border bg-surface p-0.5"
    >
      {PRESETS.map((preset) => {
        const checked = preset.value === value
        return (
          <label
            key={preset.value}
            className={cn(
              'cursor-pointer rounded-sm px-3 py-1 text-sm font-semibold transition-colors',
              // Focus lives on the hidden input, so the ring is drawn here.
              'focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand',
              checked
                ? 'bg-brand-soft text-brand-ink'
                : 'text-ink-secondary hover:bg-canvas-tint hover:text-ink',
            )}
          >
            <input
              type="radio"
              name={name}
              value={preset.value}
              checked={checked}
              onChange={() => onChange(preset.value)}
              className="sr-only"
            />
            {preset.label}
          </label>
        )
      })}
    </div>
  )
}
