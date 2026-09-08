import { cloneElement, useEffect, useId, useRef, useState } from 'react'
import type { FocusEvent, MouseEvent, ReactElement } from 'react'

export interface TooltipTriggerProps {
  onMouseEnter?: (event: MouseEvent<HTMLElement>) => void
  onMouseLeave?: (event: MouseEvent<HTMLElement>) => void
  onFocus?: (event: FocusEvent<HTMLElement>) => void
  onBlur?: (event: FocusEvent<HTMLElement>) => void
  'aria-describedby'?: string
}

export interface TooltipProps {
  content: string
  children: ReactElement<TooltipTriggerProps>
}

const SHOW_DELAY_MS = 300

export function Tooltip({ content, children }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const id = useId()
  const timeoutRef = useRef<number | undefined>(undefined)

  // Clean up pending show timeout on unmount to prevent setIsVisible on unmounted component
  useEffect(() => {
    return () => window.clearTimeout(timeoutRef.current)
  }, [])

  const show = () => {
    timeoutRef.current = window.setTimeout(() => setIsVisible(true), SHOW_DELAY_MS)
  }
  const hide = () => {
    window.clearTimeout(timeoutRef.current)
    setIsVisible(false)
  }

  const trigger = cloneElement(children, {
    onMouseEnter: (event: MouseEvent<HTMLElement>) => {
      children.props.onMouseEnter?.(event)
      show()
    },
    onMouseLeave: (event: MouseEvent<HTMLElement>) => {
      children.props.onMouseLeave?.(event)
      hide()
    },
    onFocus: (event: FocusEvent<HTMLElement>) => {
      children.props.onFocus?.(event)
      show()
    },
    onBlur: (event: FocusEvent<HTMLElement>) => {
      children.props.onBlur?.(event)
      hide()
    },
    'aria-describedby': isVisible ? id : undefined,
  })

  return (
    <span className="relative inline-block">
      {trigger}
      {isVisible ? (
        <span
          role="tooltip"
          id={id}
          className="absolute bottom-full left-1/2 z-50 mb-1 -translate-x-1/2 whitespace-nowrap rounded-sm bg-ink px-2 py-1 text-xs text-ink-inverse"
        >
          {content}
        </span>
      ) : null}
    </span>
  )
}
