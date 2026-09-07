import type { ReactNode } from 'react'

import { Button } from './Button'

export interface FilterBarProps {
  children: ReactNode
  onClear?: () => void
  hasActiveFilters?: boolean
}

export function FilterBar({ children, onClear, hasActiveFilters }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {children}
      {onClear ? (
        <Button variant="ghost" size="sm" onClick={onClear} disabled={!hasActiveFilters}>
          Clear filters
        </Button>
      ) : null}
    </div>
  )
}
