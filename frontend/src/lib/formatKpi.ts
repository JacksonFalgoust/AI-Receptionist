import type { Kpi } from '@/types'

import { formatDuration } from './formatDate'

/**
 * Turns a `Kpi` into the string a card shows. `Kpi.format` has been part of the
 * domain model since A2 but nothing rendered it, so a rate would have read "20"
 * and a duration "303" the moment either appeared on a screen.
 *
 * Locale is pinned to en-US for the same reason `formatDate` pins it: output
 * stays deterministic in tests and identical across users until the product
 * supports localised formats.
 */
export function formatKpi(kpi: Kpi): string {
  switch (kpi.format) {
    case 'percent':
      return `${kpi.value}%`
    case 'duration':
      return formatDuration(kpi.value)
    default:
      return kpi.value.toLocaleString('en-US')
  }
}
