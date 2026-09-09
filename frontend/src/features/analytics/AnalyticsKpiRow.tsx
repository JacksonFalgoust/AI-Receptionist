import { useQuery } from '@tanstack/react-query'

import { KpiCard } from '@/components/ui/KpiCard'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { formatKpi } from '@/lib/formatKpi'
import { analyticsService } from '@/services/analyticsService'
import type { DateRange } from '@/types'

/** Three across on a wide screen, still readable stacked on a phone. */
const GRID = 'grid grid-cols-1 gap-3 sm:grid-cols-3'

export interface AnalyticsKpiRowProps {
  range: DateRange
}

/**
 * US-4.1: Total conversations, Escalation rate, Avg duration — and explicitly
 * no conversion rate. The service decides which three and in what order, so
 * this renders whatever it returns rather than naming them again here.
 *
 * No empty state: zero conversations in a window is a real answer.
 */
export function AnalyticsKpiRow({ range }: AnalyticsKpiRowProps) {
  const query = useQuery({
    queryKey: ['analytics', 'summary', range],
    queryFn: () => analyticsService.getSummary(range),
  })

  return (
    <section aria-label="Performance metrics">
      <QueryBoundary query={query} loading={<KpiRowSkeleton />}>
        {(summary) => (
          <div className={GRID}>
            {summary.kpis.map((kpi) => (
              <KpiCard key={kpi.id} label={kpi.label} value={formatKpi(kpi)} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </section>
  )
}

/**
 * Holds the row's real shape while it loads so the page does not reflow. One
 * status region for the row — three would announce the same thing three times.
 */
function KpiRowSkeleton() {
  return (
    <div role="status" aria-label="Loading performance metrics" className={`${GRID} animate-pulse`}>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="rounded-lg border border-border bg-surface p-4">
          {/* Heights match KpiCard's label and value line boxes exactly. */}
          <div className="h-4 w-32 rounded bg-canvas-tint" />
          <div className="mt-1 h-8 w-16 rounded bg-canvas-tint" />
        </div>
      ))}
    </div>
  )
}
