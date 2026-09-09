import { PageHeader } from '@/components/ui/PageHeader'
import { ConciergeStatusCard } from '@/features/overview/ConciergeStatusCard'
import { OverviewKpiRow } from '@/features/overview/OverviewKpiRow'
import { RecentActivityCard } from '@/features/overview/RecentActivityCard'
import { RecentEscalationsCard } from '@/features/overview/RecentEscalationsCard'

/**
 * US-2.1: the post-login landing screen. B5 adds the date-scope control.
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
        {/*
          The prototype's `dash-grid`: state on the left, the feed beside it, so
          "is Concierge healthy" and "what did it just do" are read together.
          One column below `lg` — the feed is unreadable much narrower than half
          a laptop screen.
        */}
        <section
          aria-label="Status and recent activity"
          className="grid gap-4 lg:grid-cols-[1.15fr_1fr]"
        >
          <ConciergeStatusCard />
          <RecentActivityCard />
        </section>
        {/* Full width: five columns do not fit beside another panel. */}
        <RecentEscalationsCard />
      </div>
    </div>
  )
}
