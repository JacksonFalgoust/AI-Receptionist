import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'

import { cn } from '@/lib/cn'
import type { SemanticTone } from '@/lib/statusTone'

export type ToastTone = Exclude<SemanticTone, 'muted'>

export interface ToastOptions {
  tone?: ToastTone
  durationMs?: number
}

interface ToastRecord {
  id: string
  message: string
  tone: ToastTone
}

interface ToastContextValue {
  show: (message: string, options?: ToastOptions) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const AUTO_DISMISS_TONES: ToastTone[] = ['success', 'info']
const DEFAULT_DURATION_MS = 4000

const TOAST_TONE_CLASSES: Record<ToastTone, string> = {
  success: 'bg-success text-ink-inverse',
  info: 'bg-info text-ink-inverse',
  warning: 'bg-warning text-ink-inverse',
  danger: 'bg-danger text-ink-inverse',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([])
  // Track auto-dismiss timeouts so we can cancel them on manual dismiss or provider unmount
  const timeoutsRef = useRef<Map<string, number>>(new Map())

  const dismiss = useCallback((id: string) => {
    const handle = timeoutsRef.current.get(id)
    if (handle !== undefined) {
      window.clearTimeout(handle)
      timeoutsRef.current.delete(id)
    }
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  // Clean up any pending timers on unmount
  useEffect(() => {
    const timeouts = timeoutsRef.current
    return () => {
      for (const handle of timeouts.values()) {
        window.clearTimeout(handle)
      }
      timeouts.clear()
    }
  }, [])

  const show = useCallback(
    (message: string, options?: ToastOptions) => {
      const tone = options?.tone ?? 'info'
      const id = crypto.randomUUID()
      setToasts((current) => [...current, { id, message, tone }])
      if (AUTO_DISMISS_TONES.includes(tone)) {
        const duration = options?.durationMs ?? DEFAULT_DURATION_MS
        const handle = window.setTimeout(() => dismiss(id), duration)
        timeoutsRef.current.set(id, handle)
      }
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div
        data-testid="toast-stack"
        className="fixed bottom-4 right-4 z-[80] flex flex-col gap-2"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={cn(
              'min-w-56 rounded-sm px-4 py-3 text-sm font-semibold shadow-md',
              TOAST_TONE_CLASSES[toast.tone],
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <span>{toast.message}</span>
              <button
                type="button"
                aria-label="Dismiss"
                onClick={() => dismiss(toast.id)}
                className="text-ink-inverse/80 hover:text-ink-inverse"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
