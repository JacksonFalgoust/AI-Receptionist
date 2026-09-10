import type { SelectOption } from '@/components/ui/Select'

/**
 * Guards a small curated option list against a saved value it doesn't cover
 * (a legacy value, or one this demo's catalog just hasn't listed) — without
 * this, a native `<select>` silently reads back as `''` the moment its bound
 * value matches no `<option>`, which looks like the field lost its setting
 * and risks overwriting it with an empty value on the next save.
 */
export function withCurrentValue(options: SelectOption[], value: string): SelectOption[] {
  if (value === '' || options.some((option) => option.value === value)) return options
  return [...options, { value, label: value }]
}

/**
 * The same guard, for a set of checkboxes bound to a string-array field
 * instead of a single `<select>` — a saved value with no matching checkbox
 * in the DOM disappears from the array the moment the field mounts, since
 * react-hook-form derives a checkbox-array's value from what's actually
 * rendered and checked.
 */
export function withCurrentValues(options: SelectOption[], values: string[]): SelectOption[] {
  const known = new Set(options.map((option) => option.value))
  const missing = [...new Set(values.filter((value) => value !== '' && !known.has(value)))]
  return [...options, ...missing.map((value) => ({ value, label: value }))]
}
