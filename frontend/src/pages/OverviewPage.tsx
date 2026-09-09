import { PageHeader } from '@/components/ui/PageHeader'
import { ConciergeStatusCard } from '@/features/overview/ConciergeStatusCard'
import { OverviewKpiRow } from '@/features/overview/OverviewKpiRow'

/**
 * US-2.1: the post-login landing screen. B3 and B4 add Recent Activity and
 * Recent Escalations below the status card — B3 also introduces the two-column
 * grid the prototype pairs them in. B5 adds the date-scope control.
 */
export function OverviewPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Overview"
        description="See what Concierge is doing, how it is performing, and where humans are needed."
      />
      <div className="space-y-4">
        <OverviewKpiRow />
        <ConciergeStatusCard />
      </div>
    </div>
  )
}
