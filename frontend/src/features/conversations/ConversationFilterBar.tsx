import { useState } from 'react'
import { X } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { FilterBar } from '@/components/ui/FilterBar'
import { SearchInput } from '@/components/ui/SearchInput'
import { Select } from '@/components/ui/Select'
import { CHANNEL_LABELS } from '@/lib/channelLabels'
import { statusTone } from '@/lib/statusTone'
import type { Channel, ConversationFilterOptions, ConversationOutcome } from '@/types'

import type { ConversationFilterState, RangeChoice } from './useConversationFilters'

const ANY = ''

const CHANNEL_OPTIONS = [
  { value: ANY, label: 'Any channel' },
  ...(['voice', 'sms', 'web', 'other'] as Channel[]).map((channel) => ({
    value: channel,
    label: CHANNEL_LABELS[channel],
  })),
]

const OUTCOME_OPTIONS = [
  { value: ANY, label: 'Any outcome' },
  ...(
    ['completed', 'escalated', 'abandoned', 'failed', 'follow_up_required'] as ConversationOutcome[]
  ).map((outcome) => ({ value: outcome, label: statusTone(outcome).label })),
]

const ESCALATED_OPTIONS = [
  { value: ANY, label: 'Any' },
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
]

const RANGE_OPTIONS = [
  { value: 'any', label: 'Any time' },
  { value: 'today', label: 'Today' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
]

export interface ConversationFilterBarProps {
  state: ConversationFilterState
  options?: ConversationFilterOptions
  activeCount: number
  onChange: (patch: Partial<ConversationFilterState>) => void
  onClear: () => void
}

/** A labelled select; the label is what the tests and screen readers address it by. */
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
        className="mt-0.5 w-44"
        value={value}
        options={options}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
      />
    </label>
  )
}

/**
 * US-3.1's seven filters. Four are always visible — the set the prototype
 * shows — and the rest sit behind a disclosure so the first result row is not
 * pushed off a laptop screen. Anything applied appears as a chip, so a filter
 * hidden inside the disclosure is never silently in force.
 */
export function ConversationFilterBar({
  state,
  options,
  activeCount,
  onChange,
  onClear,
}: ConversationFilterBarProps) {
  const [expanded, setExpanded] = useState(false)

  const chips = [
    state.search && { key: 'Search', label: `"${state.search}"`, patch: { search: '' } },
    state.channel && {
      key: 'Channel',
      label: CHANNEL_LABELS[state.channel],
      patch: { channel: undefined },
    },
    state.outcome && {
      key: 'Outcome',
      label: statusTone(state.outcome).label,
      patch: { outcome: undefined },
    },
    state.escalated !== undefined && {
      key: 'Escalated',
      label: state.escalated ? 'Escalated' : 'Not escalated',
      patch: { escalated: undefined },
    },
    state.range !== 'any' && {
      key: 'Date range',
      label: RANGE_OPTIONS.find((option) => option.value === state.range)?.label ?? state.range,
      patch: { range: 'any' as RangeChoice },
    },
    state.intent && { key: 'Intent', label: state.intent, patch: { intent: undefined } },
    state.locationId && {
      key: 'Location',
      label:
        options?.locations.find((location) => location.id === state.locationId)?.name ??
        state.locationId,
      patch: { locationId: undefined },
    },
    state.assignedEmployee && {
      key: 'Assigned employee',
      label: state.assignedEmployee,
      patch: { assignedEmployee: undefined },
    },
  ].filter(Boolean) as { key: string; label: string; patch: Partial<ConversationFilterState> }[]

  return (
    <div className="space-y-2">
      <FilterBar onClear={onClear} hasActiveFilters={activeCount > 0}>
        <div className="w-72">
          <SearchInput
            aria-label="Search conversations"
            placeholder="Customer, phone, ID, intent, or keyword"
            value={state.search}
            onChange={(search) => onChange({ search })}
          />
        </div>
        <Filter
          label="Channel"
          value={state.channel ?? ANY}
          options={CHANNEL_OPTIONS}
          onChange={(value) => onChange({ channel: (value || undefined) as Channel | undefined })}
        />
        <Filter
          label="Outcome"
          value={state.outcome ?? ANY}
          options={OUTCOME_OPTIONS}
          onChange={(value) =>
            onChange({ outcome: (value || undefined) as ConversationOutcome | undefined })
          }
        />
        <Filter
          label="Escalated"
          value={state.escalated === undefined ? ANY : String(state.escalated)}
          options={ESCALATED_OPTIONS}
          onChange={(value) => onChange({ escalated: value === ANY ? undefined : value === 'true' })}
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((open) => !open)}
          aria-expanded={expanded}
        >
          {expanded ? 'Fewer filters' : 'More filters'}
        </Button>
      </FilterBar>

      {expanded ? (
        <div className="flex flex-wrap items-end gap-2">
          <Filter
            label="Date range"
            value={state.range}
            options={RANGE_OPTIONS}
            onChange={(value) => onChange({ range: value as RangeChoice })}
          />
          <Filter
            label="Intent"
            value={state.intent ?? ANY}
            options={[
              { value: ANY, label: 'Any intent' },
              ...(options?.intents ?? []).map((intent) => ({ value: intent, label: intent })),
            ]}
            onChange={(value) => onChange({ intent: value || undefined })}
          />
          <Filter
            label="Location"
            value={state.locationId ?? ANY}
            options={[
              { value: ANY, label: 'Any location' },
              ...(options?.locations ?? []).map((location) => ({
                value: location.id,
                label: location.name,
              })),
            ]}
            onChange={(value) => onChange({ locationId: value || undefined })}
          />
          <Filter
            label="Assigned employee"
            value={state.assignedEmployee ?? ANY}
            options={[
              { value: ANY, label: 'Anyone' },
              ...(options?.employees ?? []).map((employee) => ({
                value: employee,
                label: employee,
              })),
            ]}
            onChange={(value) => onChange({ assignedEmployee: value || undefined })}
          />
        </div>
      ) : null}

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
