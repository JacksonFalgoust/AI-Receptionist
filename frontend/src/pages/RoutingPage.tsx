import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { KpiCard } from '@/components/ui/KpiCard'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { RoutingRuleModal } from '@/features/routing/RoutingRuleModal'
import { RoutingRulesTable } from '@/features/routing/RoutingRulesTable'
import { ROUTING_RULES_KEY } from '@/features/routing/RuleStatusToggle'
import { dashboardService } from '@/services/dashboardService'
import { routingService } from '@/services/routingService'
import type { RoutingRule } from '@/types'

/**
 * US-10.1 / PRD §18. Two summary stats rather than the prototype's three:
 * "Avg pickup" has no data behind it — `Escalation` records when an escalation
 * was raised, never when a person picked it up — and US-10.1 marks the stats
 * optional, so the number is left out rather than invented.
 */
export function RoutingPage() {
  const rulesQuery = useQuery({
    queryKey: ROUTING_RULES_KEY,
    queryFn: () => routingService.list(),
  })

  const escalationsQuery = useQuery({
    queryKey: ['dashboard', 'escalations', 'count', 'today'],
    queryFn: () => dashboardService.countEscalations({ preset: 'today' }),
  })

  // Derived from the rules already loaded rather than queried separately, so
  // it moves the instant a row's toggle patches the cache.
  const activeRules = (rulesQuery.data ?? []).filter((rule) => rule.enabled).length

  const [isCreating, setCreating] = useState(false)
  const [editingRule, setEditingRule] = useState<RoutingRule | null>(null)
  // Snapshotted at the moment "Add rule" is clicked, not recomputed on every
  // render. `defaultPriority={rules.length + 1}` used to be passed straight
  // through live: if the rules query was still loading when the modal opened
  // (rules.length === 0) and then resolved while the modal stayed open, the
  // prop's value would jump, `RoutingRuleModal`'s reset effect would see that
  // change and fire again, and an in-progress "Add rule" form would be
  // silently wiped mid-edit. Freezing the value at click time removes the
  // only thing that could change out from under an open modal.
  const [pendingPriority, setPendingPriority] = useState(1)

  const rules = rulesQuery.data ?? []
  const isModalOpen = isCreating || editingRule !== null

  function openCreateModal() {
    setPendingPriority(rules.length + 1)
    setCreating(true)
  }

  function closeModal() {
    setCreating(false)
    setEditingRule(null)
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Escalation & Routing"
        description="Control when and how Concierge hands a customer to a person."
        actions={<Button onClick={openCreateModal}>Add rule</Button>}
      />

      {/* Rendered above the boundary so the page keeps its shape while the
          table loads and nothing reflows when the rows land. */}
      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <KpiCard label="Active rules" value={rulesQuery.isPending ? '—' : activeRules} />
        <KpiCard
          label="Escalations today"
          value={escalationsQuery.isPending ? '—' : (escalationsQuery.data ?? 0)}
        />
      </div>

      <Panel>
        <QueryBoundary
          query={rulesQuery}
          skeletonRows={6}
          isEmpty={(loaded) => loaded.length === 0}
          empty={{
            title: 'Create your first routing rule',
            description:
              'Rules decide when Concierge hands a conversation to a person, and who receives it.',
            action: { label: 'Add rule', onClick: openCreateModal },
          }}
        >
          {(loaded) => (
            <RoutingRulesTable
              rules={loaded}
              renderRowAction={(rule) => (
                <Button variant="ghost" size="sm" onClick={() => setEditingRule(rule)}>
                  Edit
                </Button>
              )}
            />
          )}
        </QueryBoundary>
      </Panel>

      <RoutingRuleModal
        isOpen={isModalOpen}
        onClose={closeModal}
        rule={editingRule ?? undefined}
        // A new rule lands after the rules that already exist rather than
        // colliding with the top of the evaluation order. Snapshotted in
        // `openCreateModal`, not derived live — see the comment on
        // `pendingPriority` above.
        defaultPriority={pendingPriority}
      />
    </div>
  )
}
