import { forwardRef } from 'react'
import type { InputHTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid, className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      {...props}
      aria-invalid={invalid || props['aria-invalid'] || undefined}
      className={cn(
        'w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand/40 aria-invalid:border-danger',
        className,
      )}
    />
  )
})
