import { cloneElement, useEffect, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent, ReactElement, ReactNode } from 'react'

import { cn } from '@/lib/cn'
import { isTopEscapeHandler, popEscapeHandler, pushEscapeHandler } from '@/lib/escapeStack'

export interface DropdownTriggerProps {
  onClick?: (event: ReactMouseEvent<HTMLElement>) => void
  'aria-haspopup'?: 'menu' | 'dialog'
  'aria-expanded'?: boolean
}

export interface DropdownProps {
  trigger: ReactElement<DropdownTriggerProps>
  children: ReactNode
  align?: 'start' | 'end'
  /**
   * `menu` for a list of actions; `dialog` for an informational popover such as
   * the Concierge status or notification panels, where menu-item semantics
   * would misdescribe the content.
   */
  role?: 'menu' | 'dialog'
  /** Accessible name for the panel. Supply it whenever `role` is `dialog`. */
  label?: string
}

export function Dropdown({ trigger, children, align = 'start', role = 'menu', label }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return

    const escapeHandlerId = pushEscapeHandler()

    function handlePointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isTopEscapeHandler(escapeHandlerId)) setIsOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
      popEscapeHandler(escapeHandlerId)
    }
  }, [isOpen])

  const triggerWithHandlers = cloneElement(trigger, {
    onClick: (event: ReactMouseEvent<HTMLElement>) => {
      trigger.props.onClick?.(event)
      setIsOpen((open) => !open)
    },
    'aria-haspopup': role,
    'aria-expanded': isOpen,
  })

  return (
    <div ref={rootRef} className="relative inline-block">
      {triggerWithHandlers}
      {isOpen ? (
        <div
          role={role}
          aria-label={role === 'dialog' ? label : undefined}
          className={cn(
            'absolute z-40 mt-1 min-w-40 rounded-md border border-border bg-surface p-1 shadow-md',
            align === 'end' ? 'right-0' : 'left-0',
          )}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}
