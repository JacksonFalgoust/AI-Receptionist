import { KpiCard } from '@/components/ui/KpiCard'
import type { BookingSummary } from '@/types'

const GRID = 'grid grid-cols-2 gap-3 md:grid-cols-4'

export function BookingSummaryRow({ summary }: { summary: BookingSummary }) {
  return (
    <section aria-label="Booking summary">
      <div className={GRID}>
        <KpiCard label="Pickups today" value={summary.pickupsToday} />
        <KpiCard label="Returns today" value={summary.returnsToday} />
        <KpiCard label="Next 7 days" value={summary.next7Days} />
        <KpiCard label="Unpaid" value={summary.unpaid} />
      </div>
    </section>
  )
}

/** Holds the row's shape while the first load is in flight. */
export function BookingSummarySkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading booking summary"
      className={`${GRID} animate-pulse`}
    >
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="rounded-lg border border-border bg-surface p-4">
          <div className="h-4 w-24 rounded bg-canvas-tint" />
          <div className="mt-1 h-8 w-12 rounded bg-canvas-tint" />
        </div>
      ))}
    </div>
  )
}
