import { PageHeader } from '@/components/ui/PageHeader'
import { OverviewKpiRow } from '@/features/overview/OverviewKpiRow'

/**
 * US-2.1: the post-login landing screen. B2–B4 add the Concierge Status card,
 * Recent Activity, and Recent Escalations below the KPI row; B5 adds the
 * date-scope control that feeds every one of them.
 */
export function OverviewPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Overview"
        description="See what Concierge is doing, how it is performing, and where humans are needed."
      />
      <OverviewKpiRow />
    </div>
  )
}
