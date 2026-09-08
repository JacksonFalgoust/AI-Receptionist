import { forwardRef } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/cn'
import type { ButtonSize, ButtonVariant } from './Button'

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  icon: ReactNode
  variant?: ButtonVariant
  size?: ButtonSize
  /** Required — an icon-only button has no other accessible name. */
  'aria-label': string
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-brand text-ink-inverse hover:bg-brand-strong',
  ghost: 'text-ink-secondary hover:bg-canvas-tint',
  danger: 'text-danger hover:bg-danger-soft',
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-7 w-7',
  md: 'h-9 w-9',
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon, variant = 'ghost', size = 'md', className, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex items-center justify-center rounded-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      {...props}
    >
      {icon}
    </button>
  )
})
