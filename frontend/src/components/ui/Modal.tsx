import { useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { useFocusTrap } from '@/lib/useFocusTrap'

export interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  actions?: ReactNode
}

export function Modal({ isOpen, onClose, title, children, actions }: ModalProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  useFocusTrap(containerRef, isOpen, onClose)

  if (!isOpen) return null

  const stopPropagation = (event: MouseEvent<HTMLDivElement>) => event.stopPropagation()

  return createPortal(
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/45 p-4"
      onClick={onClose}
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onClick={stopPropagation}
        className="w-full max-w-md rounded-lg bg-surface p-6 shadow-md"
      >
        <h2 className="mb-1 text-lg font-semibold text-ink">{title}</h2>
        <div className="text-sm text-ink-secondary">{children}</div>
        {actions ? <div className="mt-4 flex justify-end gap-2">{actions}</div> : null}
      </div>
    </div>,
    document.body,
  )
}
