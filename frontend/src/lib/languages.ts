import type { SelectOption } from '@/components/ui/Select'

/**
 * A small curated set of languages for the Identity tab's Primary language
 * select and Supported languages checkboxes — enough to cover this demo's
 * seed data (`en-US`/`es-US`), not a full locale catalog.
 */
export const LANGUAGE_OPTIONS: SelectOption[] = [
  { value: 'en-US', label: 'English (US)' },
  { value: 'es-US', label: 'Spanish (US)' },
  { value: 'fr-CA', label: 'French (Canada)' },
  { value: 'pt-BR', label: 'Portuguese (Brazil)' },
]
