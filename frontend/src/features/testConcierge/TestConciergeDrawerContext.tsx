import { useMutation } from '@tanstack/react-query'
import { createContext, useCallback, useState } from 'react'
import type { ReactNode } from 'react'

import { testConciergeService } from '@/services/testConciergeService'
import type { TestConciergeTurn } from '@/types'

export interface TestConciergeDrawerContextValue {
  isOpen: boolean
  open: () => void
  close: () => void
  /** Oldest first. Survives closing the drawer and navigating pages; resets
   * on a full reload, like every other client-only state in this app. */
  turns: TestConciergeTurn[]
  /** The customer's message, shown immediately, before its reply resolves. */
  pendingMessage: string | null
  isSending: boolean
  send: (message: string) => Promise<void>
  clear: () => void
}

export const TestConciergeDrawerContext =
  createContext<TestConciergeDrawerContextValue | null>(null)

/**
 * Mounted once in `App.tsx`, above `AppRoutes` — the same reason
 * `ToastProvider`/`ConfirmDialogProvider` sit there. This is what makes the
 * test conversation outlive closing the drawer and switching pages.
 */
export function TestConciergeDrawerProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)
  const [turns, setTurns] = useState<TestConciergeTurn[]>([])
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (message: string) => testConciergeService.simulate(message),
  })

  const send = useCallback(
    async (message: string) => {
      setPendingMessage(message)
      try {
        const reply = await mutation.mutateAsync(message)
        setTurns((prev) => [...prev, { ...reply, customerMessage: message }])
        setPendingMessage(null)
      } catch (error) {
        // The message is not added to `turns` on failure — the caller (the
        // panel) shows its own inline error and the customer can retype.
        setPendingMessage(null)
        throw error
      }
    },
    [mutation],
  )

  const open = useCallback(() => setIsOpen(true), [])
  const close = useCallback(() => setIsOpen(false), [])
  const clear = useCallback(() => setTurns([]), [])

  return (
    <TestConciergeDrawerContext.Provider
      value={{
        isOpen,
        open,
        close,
        turns,
        pendingMessage,
        isSending: mutation.isPending,
        send,
        clear,
      }}
    >
      {children}
    </TestConciergeDrawerContext.Provider>
  )
}
