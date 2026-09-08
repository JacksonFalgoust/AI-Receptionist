import { useQuery } from '@tanstack/react-query'
import { Check, ChevronDown } from 'lucide-react'

import { Dropdown } from '@/components/ui/Dropdown'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/useAuth'
import { organizationService } from '@/services/organizationService'

/**
 * PRD §6.2 organization selector. One organization today, so the list is real
 * plumbing of length one — Phase F's multi-organization switching swaps the
 * data and removes the note, without rewriting the control.
 */
export function OrganizationMenu() {
  const { user } = useAuth()
  const query = useQuery({
    queryKey: ['organizations'],
    queryFn: () => organizationService.list(),
  })

  if (!user) return null

  return (
    <Dropdown
      role="dialog"
      label="Organizations"
      trigger={
        <button
          type="button"
          aria-label={`Organization: ${user.organizationName}`}
          className="flex items-center gap-2 rounded-sm border border-border px-3 py-1.5 text-sm font-semibold hover:bg-canvas"
        >
          <span className="size-2 rounded-full bg-brand" aria-hidden="true" />
          {user.organizationName}
          <ChevronDown className="size-3.5 text-ink-muted" aria-hidden="true" />
        </button>
      }
    >
      <div className="w-64">
        <QueryBoundary query={query} skeletonRows={2}>
          {(organizations) => (
            <ul>
              {organizations.map((organization) => (
                <li
                  key={organization.id}
                  className="flex items-start justify-between gap-2 rounded-sm px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-semibold text-ink">{organization.name}</p>
                    <p className="text-xs text-ink-muted">
                      {organization.locations.length}{' '}
                      {organization.locations.length === 1 ? 'office' : 'offices'}
                    </p>
                  </div>
                  {organization.id === user.organizationId ? (
                    <>
                      <Check className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden="true" />
                      <span className="sr-only">Current organization</span>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </QueryBoundary>

        <p className="mt-1 border-t border-border px-3 pt-2 pb-1 text-xs text-ink-muted">
          Switching between organizations arrives with multi-organization support.
        </p>
      </div>
    </Dropdown>
  )
}
