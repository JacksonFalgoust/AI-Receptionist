import { useState } from 'react'

import { EmptyState } from '@/components/ui/EmptyState'
import { PageHeader } from '@/components/ui/PageHeader'
import { SearchInput } from '@/components/ui/SearchInput'
import { HelpResourceCard } from '@/features/help/HelpResourceCard'
import { HELP_RESOURCES } from '@/features/help/helpResources'
import type { HelpResource } from '@/features/help/helpResources'

/**
 * Case-insensitive substring match against title and description. Not the
 * mocks-layer `matchesSearch` from `mocks/query.ts` — PRD §38 reserves
 * `src/mocks/` imports to files under `src/services/`, and a presentational
 * page must not reach past that boundary even for a two-line check. One
 * call site does not justify a new shared `lib/` helper either.
 */
function matchesQuery(resource: HelpResource, query: string): boolean {
  const term = query.trim().toLowerCase()
  if (!term) return true
  return (
    resource.title.toLowerCase().includes(term) ||
    resource.description.toLowerCase().includes(term)
  )
}

/** US-14.1 / PRD §23. Ungated — every authenticated role reaches this page. */
export function HelpPage() {
  const [query, setQuery] = useState('')
  const filtered = HELP_RESOURCES.filter((resource) => matchesQuery(resource, query))

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Help"
        description="Guides for configuring, connecting, and operating Concierge."
      />

      <SearchInput
        value={query}
        onChange={setQuery}
        placeholder="Search guides"
        aria-label="Search help"
      />

      <div className="mt-4">
        {filtered.length === 0 ? (
          <EmptyState title="No results" description="Try a different search term." />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((resource) => (
              <HelpResourceCard key={resource.title} resource={resource} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
