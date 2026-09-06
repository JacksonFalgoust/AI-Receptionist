import { forwardRef, useId } from 'react'
import type { InputHTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

export interface RadioProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(function Radio(
  { label, className, id, type: _type, ...props },
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
        type="radio"
        className={cn(
          'h-4 w-4 border border-border-strong accent-brand focus:outline-none focus:ring-2 focus:ring-brand/40',
          className,
        )}
      />
      {label}
    </label>
  )
})
