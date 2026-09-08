import { useEffect, useRef } from 'react'
import { Search } from 'lucide-react'

import { Input } from './Input'

export interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  onSearch?: (value: string) => void
  debounceMs?: number
  placeholder?: string
  'aria-label': string
}

export function SearchInput({
  value,
  onChange,
  onSearch,
  debounceMs = 300,
  placeholder,
  ...rest
}: SearchInputProps) {
  // Keep a ref to the latest onSearch callback. Callers typically pass an
  // inline arrow that gets a new identity on every render; including
  // onSearch in the effect deps would tear down and re-arm the debounce
  // timer on every unrelated parent re-render, potentially starving search
  // indefinitely.
  const onSearchRef = useRef(onSearch)
  // oxlint-disable-next-line react/refs
  onSearchRef.current = onSearch
  // Skip the debounce fire on mount so an unchanged initial value doesn't
  // trigger a spurious search after debounceMs.
  const isFirstRun = useRef(true)

  useEffect(() => {
    if (isFirstRun.current) {
      isFirstRun.current = false
      return
    }
    if (!onSearchRef.current) return
    const handle = window.setTimeout(() => onSearchRef.current?.(value), debounceMs)
    return () => window.clearTimeout(handle)
  }, [value, debounceMs])

  return (
    <div className="relative">
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted"
        aria-hidden
      />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="pl-8"
        {...rest}
      />
    </div>
  )
}
