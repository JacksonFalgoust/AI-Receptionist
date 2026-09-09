import { useState } from 'react'

import { DateScope } from '@/components/ui/DateScope'
import { PageHeader } from '@/components/ui/PageHeader'
import { AnalyticsKpiRow } from '@/features/analytics/AnalyticsKpiRow'
import { TopIntentsTable } from '@/features/analytics/TopIntentsTable'
import type { DateRange } from '@/types'

/**
 * US-4.1: historical performance. Opens on 30 days rather than Overview's
 * today — this screen exists to review effectiveness over a period, and a
 * single day is too short a window to read anything from.
 *
 * No Export, and no conversion rate: US-4.1 excludes both.
 */
export function AnalyticsPage() {
  const [range, setRange] = useState<DateRange>({ preset: '30d' })

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Analytics"
        description="Historical performance and business intelligence for your Concierge."
        actions={<DateScope value={range.preset} onChange={(preset) => setRange({ preset })} />}
      />
      <div className="space-y-4">
        <AnalyticsKpiRow range={range} />
        <TopIntentsTable range={range} />
      </div>
    </div>
  )
}
