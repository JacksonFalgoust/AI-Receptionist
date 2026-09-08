import { forwardRef, useId } from 'react'
import type { InputHTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

export interface ToggleProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
}

export const Toggle = forwardRef<HTMLInputElement, ToggleProps>(function Toggle(
  { label, className, id, type: _type, role: _role, ...props },
  ref,
) {
  const generatedId = useId()
  const inputId = id ?? generatedId

  return (
    <label htmlFor={inputId} className="inline-flex items-center gap-2 text-sm text-ink">
      <input
        ref={ref}
        {...props}
        id={inputId}
        type="checkbox"
        role="switch"
        className={cn(
          'h-5 w-9 appearance-none rounded-full bg-border-strong transition-colors checked:bg-brand focus:outline-none focus:ring-2 focus:ring-brand/40',
          className,
        )}
      />
      {label}
    </label>
  )
})
