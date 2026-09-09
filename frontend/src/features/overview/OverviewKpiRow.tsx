import { useQuery } from '@tanstack/react-query'

import { KpiCard } from '@/components/ui/KpiCard'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { formatKpi } from '@/lib/formatKpi'
import { dashboardService } from '@/services/dashboardService'
import type { DateRange } from '@/types'

/** Overview lands on today; B5's date-scope control passes a wider range in. */
const DEFAULT_RANGE: DateRange = { preset: 'today' }

/** Five across on a wide screen, still readable two-up on a phone. */
const GRID = 'grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5'

export interface OverviewKpiRowProps {
  range?: DateRange
}

/**
 * US-2.2: the five headline numbers on Overview. The service decides which
 * five and in what order — this renders whatever it returns, so the row can
 * never drift from the counts a user drills into.
 *
 * No empty state: zero conversations is a real answer, not missing data.
 */
export function OverviewKpiRow({ range = DEFAULT_RANGE }: OverviewKpiRowProps) {
  const query = useQuery({
    queryKey: ['dashboard', 'overview', range],
    queryFn: () => dashboardService.getOverview(range),
  })

  return (
    <section aria-label="Key metrics">
      <QueryBoundary query={query} loading={<KpiRowSkeleton />}>
        {(overview) => (
          <div className={GRID}>
            {overview.kpis.map((kpi) => (
              <KpiCard key={kpi.id} label={kpi.label} value={formatKpi(kpi)} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </section>
  )
}

/**
 * Holds the row's real shape while it loads, so the page does not reflow when
 * the numbers land. One status region for the row — five would make a screen
 * reader announce the same thing five times.
 */
function KpiRowSkeleton() {
  return (
    <div role="status" aria-label="Loading key metrics" className={`${GRID} animate-pulse`}>
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="rounded-lg border border-border bg-surface p-4">
          {/* Heights match KpiCard's label and value line boxes exactly. */}
          <div className="h-4 w-24 rounded bg-canvas-tint" />
          <div className="mt-1 h-8 w-12 rounded bg-canvas-tint" />
        </div>
      ))}
    </div>
  )
}
