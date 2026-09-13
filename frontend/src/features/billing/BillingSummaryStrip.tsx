import type { ReactNode } from 'react'

import { StatusPill } from '@/components/ui/StatusPill'
import { formatDateRange } from '@/lib/formatDate'
import type { BillingOverview } from '@/types'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-semibold text-ink-muted">{label}</span>
      <span className="text-sm text-ink">{children}</span>
    </div>
  )
}

export interface BillingSummaryStripProps {
  billing: BillingOverview
}

/**
 * PRD §21's four headline facts, on the `Fact` pattern
 * `ConversationSummaryStrip` established.
 *
 * PRD §47 is satisfied by construction: `paymentMethod` is a display-safe
 * string in the domain model, so there is no card number here to leak.
 */
export function BillingSummaryStrip({ billing }: BillingSummaryStripProps) {
  return (
    <div className="mb-4 grid grid-cols-2 gap-4 rounded-lg border border-border bg-surface p-4 md:grid-cols-4">
      <Fact label="Current plan">{billing.planName}</Fact>
      <Fact label="Status">
        <StatusPill status={billing.status} />
      </Fact>
      <Fact label="Billing period">
        {formatDateRange(billing.periodStart, billing.periodEnd)}
      </Fact>
      <Fact label="Payment method">
        {/* The absence is the thing an owner needs to see, so it is stated
            rather than left as a blank cell. */}
        {billing.paymentMethod ?? (
          <span className="text-ink-secondary">No payment method on file</span>
        )}
      </Fact>
    </div>
  )
}
