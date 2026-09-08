import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'

import { isTopEscapeHandler, popEscapeHandler, pushEscapeHandler } from './escapeStack'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Traps Tab/Shift+Tab focus inside `containerRef` while `isActive`, invokes
 * `onEscape` on the Escape key, and restores focus to whatever element was
 * focused right before activation once it deactivates. Shared by `Modal`
 * and `Drawer`.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  isActive: boolean,
  onEscape?: () => void,
) {
  const triggerRef = useRef<HTMLElement | null>(null)
  // Keep a ref to the latest onEscape callback. Modal and Drawer pass inline
  // arrows that get a new identity on every render; including onEscape in the
  // effect deps would cause the effect to re-run on unrelated re-renders,
  // stealing focus back to the first focusable element mid-interaction.
  const onEscapeRef = useRef(onEscape)
  // oxlint-disable-next-line react/refs
  onEscapeRef.current = onEscape

  useEffect(() => {
    if (!isActive) return

    const container = containerRef.current
    triggerRef.current = document.activeElement as HTMLElement | null
    const escapeHandlerId = pushEscapeHandler()

    const focusables = () =>
      Array.from(container?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [])

    const first = focusables()[0]
    ;(first ?? container)?.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (isTopEscapeHandler(escapeHandlerId)) {
          onEscapeRef.current?.()
        }
        return
      }
      if (event.key !== 'Tab') return

      const elements = focusables()
      if (elements.length === 0) return
      const firstEl = elements[0]
      const lastEl = elements[elements.length - 1]

      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault()
        lastEl.focus()
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault()
        firstEl.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      popEscapeHandler(escapeHandlerId)
      triggerRef.current?.focus()
    }
  }, [isActive, containerRef])
}
