import { useEffect } from 'react'
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
  useEffect(() => {
    if (!onSearch) return
    const handle = window.setTimeout(() => onSearch(value), debounceMs)
    return () => window.clearTimeout(handle)
  }, [value, debounceMs, onSearch])

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
