import { useState } from 'react'
import { X } from 'lucide-react'

import { FilterBar } from '@/components/ui/FilterBar'
import { SearchInput } from '@/components/ui/SearchInput'
import { Select } from '@/components/ui/Select'
import { KNOWLEDGE_STATUSES, KNOWLEDGE_TYPES, knowledgeTypeLabel } from '@/lib/knowledgeLabels'
import { statusTone } from '@/lib/statusTone'
import type { KnowledgeStatus, KnowledgeType } from '@/types'

import type { KnowledgeFilterState } from './useKnowledgeFilters'

const ANY = ''

const TYPE_OPTIONS = [
  { value: ANY, label: 'Any type' },
  ...KNOWLEDGE_TYPES.map((type) => ({ value: type, label: knowledgeTypeLabel(type) })),
]

const STATUS_OPTIONS = [
  { value: ANY, label: 'Any status' },
  ...KNOWLEDGE_STATUSES.map((status) => ({ value: status, label: statusTone(status).label })),
]

export interface KnowledgeFilterBarProps {
  state: KnowledgeFilterState
  activeCount: number
  onChange: (patch: Partial<KnowledgeFilterState>) => void
  onClear: () => void
}

/** A labelled select; the label is what tests and screen readers address it by. */
function Filter({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <label className="text-xs font-semibold text-ink-muted">
      {label}
      <Select
        className="mt-0.5 w-48"
        value={value}
        options={options}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
      />
    </label>
  )
}

/**
 * US-5.1's search and two filters. Both selects list every value in the
 * domain, not the prototype's shortened set — the seeded library contains
 * types the prototype's four options cannot reach, which reads as a bug rather
 * than a simplification. Anything in force also appears as a chip, so a filter
 * is never silently applied.
 */
export function KnowledgeFilterBar({
  state,
  activeCount,
  onChange,
  onClear,
}: KnowledgeFilterBarProps) {
  // Local echo of the typed text so the box stays responsive while the query
  // behind it waits for a pause; when `state.search` changes from outside (a
  // chip removal, Clear filters) the box must not show stale text. Adjusting
  // during render rather than in an effect avoids painting the stale value
  // for a frame — see ConversationFilterBar for the same pattern.
  const [searchText, setSearchText] = useState(state.search)
  const [syncedSearch, setSyncedSearch] = useState(state.search)
  if (state.search !== syncedSearch) {
    setSyncedSearch(state.search)
    setSearchText(state.search)
  }

  const chips = [
    state.search && { key: 'Search', label: `"${state.search}"`, patch: { search: '' } },
    state.type && {
      key: 'Type',
      label: knowledgeTypeLabel(state.type),
      patch: { type: undefined },
    },
    state.status && {
      key: 'Status',
      label: statusTone(state.status).label,
      patch: { status: undefined },
    },
  ].filter(Boolean) as { key: string; label: string; patch: Partial<KnowledgeFilterState> }[]

  return (
    <div className="space-y-2">
      <FilterBar onClear={onClear} hasActiveFilters={activeCount > 0}>
        <div className="w-72">
          <SearchInput
            aria-label="Search knowledge"
            placeholder="Name, tag, category, or source"
            value={searchText}
            onChange={setSearchText}
            onSearch={(search) => onChange({ search })}
          />
        </div>
        <Filter
          label="Type"
          value={state.type ?? ANY}
          options={TYPE_OPTIONS}
          onChange={(value) => onChange({ type: (value || undefined) as KnowledgeType | undefined })}
        />
        <Filter
          label="Status"
          value={state.status ?? ANY}
          options={STATUS_OPTIONS}
          onChange={(value) =>
            onChange({ status: (value || undefined) as KnowledgeStatus | undefined })
          }
        />
      </FilterBar>

      {chips.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Active filters">
          {chips.map((chip) => (
            <li
              key={chip.key}
              className="inline-flex items-center gap-1 rounded-full bg-canvas-tint px-2 py-0.5 text-xs font-semibold text-ink-secondary"
            >
              <span>
                {chip.key}: {chip.label}
              </span>
              <button
                type="button"
                aria-label={`Remove ${chip.key} filter`}
                onClick={() => onChange(chip.patch)}
                className="rounded-full p-0.5 hover:bg-surface"
              >
                <X className="h-3 w-3" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
