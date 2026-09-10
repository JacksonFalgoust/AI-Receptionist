import type { SelectOption } from '@/components/ui/Select'

/**
 * A small curated set of named voices for the Identity tab's Voice field —
 * this app has no live TTS catalog to read from yet (that's GuideAnts-side,
 * wired up in E6), so these stand in the way the static prototype's own
 * three options did.
 */
export const VOICE_OPTIONS: SelectOption[] = [
  { value: 'Avery — Warm', label: 'Avery — Warm' },
  { value: 'Jordan — Clear', label: 'Jordan — Clear' },
  { value: 'Morgan — Calm', label: 'Morgan — Calm' },
]
