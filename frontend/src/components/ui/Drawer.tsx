import { useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { useFocusTrap } from '@/lib/useFocusTrap'

export interface DrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
}

export function Drawer({ isOpen, onClose, title, children, footer }: DrawerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  useFocusTrap(containerRef, isOpen, onClose)

  if (!isOpen) return null

  const stopPropagation = (event: MouseEvent<HTMLDivElement>) => event.stopPropagation()

  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink/45" onClick={onClose}>
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onClick={stopPropagation}
        className="fixed inset-y-0 right-0 flex h-full w-full max-w-md flex-col bg-surface shadow-md"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 text-sm text-ink-secondary">{children}</div>
        {footer ? <div className="border-t border-border px-4 py-3">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  )
}
