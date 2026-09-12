import { useQuery } from '@tanstack/react-query'

import { PageHeader } from '@/components/ui/PageHeader'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { BillingSummaryStrip } from '@/features/billing/BillingSummaryStrip'
import { InvoicesTable } from '@/features/billing/InvoicesTable'
import { UsageMeter } from '@/features/billing/UsageMeter'
import { billingService } from '@/services/billingService'

/**
 * US-12.1 / PRD §21. Owner and Administrator only (`manage:billing`).
 *
 * Read-only: `billingService` exposes `getOverview()` and nothing else, and
 * plan changes are not in MVP scope — so the page header carries no actions.
 * All three sections come from one call, so they share one boundary.
 */
export function BillingPage() {
  const billingQuery = useQuery({
    queryKey: ['billing', 'overview'],
    queryFn: () => billingService.getOverview(),
  })

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Billing" description="Your plan, usage, and invoices." />

      <QueryBoundary query={billingQuery} skeletonRows={6}>
        {(billing) => (
          <>
            <BillingSummaryStrip billing={billing} />

            <Panel className="mb-4">
              <PanelHeader title="Usage this period" />
              <div className="px-4 py-1">
                {billing.usage.map((metric) => (
                  <UsageMeter key={metric.id} metric={metric} />
                ))}
              </div>
            </Panel>

            <Panel>
              <PanelHeader title="Invoices" />
              <InvoicesTable invoices={billing.invoices} periodEnd={billing.periodEnd} />
            </Panel>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}
