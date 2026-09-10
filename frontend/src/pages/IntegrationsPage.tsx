import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { FilterBar } from '@/components/ui/FilterBar'
import { PageHeader } from '@/components/ui/PageHeader'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Select } from '@/components/ui/Select'
import { IntegrationCard } from '@/features/integrations/IntegrationCard'
import { INTEGRATION_CATEGORIES, integrationCategoryLabel } from '@/lib/integrationLabels'
import { integrationService } from '@/services/integrationService'
import type { Integration, IntegrationCategory } from '@/types'

const ANY = ''

const CATEGORY_OPTIONS = [
  { value: ANY, label: 'All categories' },
  ...INTEGRATION_CATEGORIES.map((category) => ({
    value: category,
    label: integrationCategoryLabel(category),
  })),
]

function byCategory(integrations: Integration[], category: IntegrationCategory | ''): Integration[] {
  return category ? integrations.filter((integration) => integration.category === category) : integrations
}

/**
 * US-9.1: the catalog only — Connect/Continue setup/Repair/Disconnect are
 * D2's. The category filter is local state, not URL state: a fixed ~10-card
 * catalog has little use for a shareable filtered link, unlike Knowledge or
 * Conversations.
 */
export function IntegrationsPage() {
  const [category, setCategory] = useState<IntegrationCategory | ''>(ANY)

  const query = useQuery({
    queryKey: ['integrations', 'list'],
    queryFn: () => integrationService.list(),
  })

  // Computed once and reused by both `isEmpty` and the grid below, so the two
  // can never disagree about what "filtered" means.
  const filtered = useMemo(() => byCategory(query.data ?? [], category), [query.data, category])
  // The empty-state copy must key off the whole catalog, not the filter: a
  // category left selected while the catalog itself has nothing in it is
  // still "connect your first business system", not "try a different
  // category" — there's nothing to connect anywhere.
  const catalogIsEmpty = (query.data?.length ?? 0) === 0

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Integrations"
        description="Connect Concierge to the business systems it needs to read from and act on."
      />
      <div className="space-y-3">
        <FilterBar onClear={() => setCategory(ANY)} hasActiveFilters={category !== ANY}>
          <label className="text-xs font-semibold text-ink-muted">
            Category
            <Select
              className="mt-0.5 w-56"
              value={category}
              options={CATEGORY_OPTIONS}
              onChange={(event) => setCategory(event.target.value as IntegrationCategory | '')}
              aria-label="Category"
            />
          </label>
        </FilterBar>

        <QueryBoundary
          query={query}
          skeletonRows={6}
          isEmpty={() => filtered.length === 0}
          empty={
            category && !catalogIsEmpty
              ? {
                  title: 'No integrations in this category',
                  description: 'Try a different category, or clear the filter.',
                }
              : {
                  // PRD §17 / US-9.1, verbatim.
                  title: 'Connect your first business system',
                }
          }
        >
          {() => (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((integration) => (
                <IntegrationCard key={integration.id} integration={integration} />
              ))}
            </div>
          )}
        </QueryBoundary>
      </div>
    </div>
  )
}
