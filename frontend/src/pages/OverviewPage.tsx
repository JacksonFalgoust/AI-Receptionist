import { useState } from 'react'

import { DateScope } from '@/components/ui/DateScope'
import { PageHeader } from '@/components/ui/PageHeader'
import { ConciergeStatusCard } from '@/features/overview/ConciergeStatusCard'
import { OverviewKpiRow } from '@/features/overview/OverviewKpiRow'
import { RecentActivityCard } from '@/features/overview/RecentActivityCard'
import { RecentEscalationsCard } from '@/features/overview/RecentEscalationsCard'
import type { DateRange } from '@/types'

/**
 * US-2.1: the post-login landing screen.
 *
 * The scope is per-visit state rather than part of the address — a manager
 * opening Overview each morning should get today, whatever they last chose.
 */
export function OverviewPage() {
  const [range, setRange] = useState<DateRange>({ preset: 'today' })

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Overview"
        description="See what Concierge is doing, how it is performing, and where humans are needed."
        // US-2.1 is explicit that Overview carries no Export action.
        actions={<DateScope value={range.preset} onChange={(preset) => setRange({ preset })} />}
      />
      <div className="space-y-4">
        <OverviewKpiRow range={range} />
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
          {/* Live state — it reports how Concierge is right now, so no range. */}
          <ConciergeStatusCard />
          <RecentActivityCard range={range} />
        </section>
        {/* Full width: five columns do not fit beside another panel. */}
        <RecentEscalationsCard range={range} />
      </div>
    </div>
  )
}
