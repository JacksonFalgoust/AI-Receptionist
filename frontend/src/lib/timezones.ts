import type { SelectOption } from '@/components/ui/Select'

/**
 * A curated set of IANA zones for the business profile's Time zone field —
 * not an exhaustive list, just enough to cover where this demo's customers
 * actually operate (US-centric, like the rest of the seed data).
 */
export const TIMEZONE_OPTIONS: SelectOption[] = [
  { value: 'America/New_York', label: 'Eastern Time (US)' },
  { value: 'America/Chicago', label: 'Central Time (US)' },
  { value: 'America/Denver', label: 'Mountain Time (US)' },
  { value: 'America/Phoenix', label: 'Mountain Time (Arizona, no DST)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (US)' },
  { value: 'America/Anchorage', label: 'Alaska Time' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time' },
  { value: 'UTC', label: 'UTC' },
]
