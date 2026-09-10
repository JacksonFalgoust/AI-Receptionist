import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/components/ui/ToastProvider'
import { toAppError } from '@/services/errors'
import { routingService } from '@/services/routingService'
import type { RoutingRule } from '@/types'

/** Shared with `RoutingPage`'s list query, so a row's own mutation can patch it directly. */
export const ROUTING_RULES_KEY = ['routing', 'rules']

export interface RuleStatusToggleProps {
  rule: RoutingRule
}

/**
 * US-10.1's inline enable/disable, doubling as PRD §18.4's Status column — one
 * control for both, so the row can never show a status that disagrees with its
 * own switch.
 *
 * Self-contained like `FeatureCard`: its own mutation, patching the shared
 * `['routing', 'rules']` cache on success. Not confirmed — a toggle is undone
 * with one click; deletion is the confirmed action on this screen.
 */
export function RuleStatusToggle({ rule }: RuleStatusToggleProps) {
  const queryClient = useQueryClient()
  const toast = useToast()

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => routingService.setEnabled(rule.id, enabled),
    onSuccess: (updated) => {
      queryClient.setQueryData<RoutingRule[]>(ROUTING_RULES_KEY, (current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)),
      )
      toast.show(
        updated.enabled
          ? `${updated.name} is now routing escalations.`
          : `${updated.name} will no longer route escalations.`,
        { tone: 'success' },
      )
    },
    onError: (error) => toast.show(toAppError(error).description, { tone: 'danger' }),
  })

  return (
    <div className="flex items-center gap-2">
      <Toggle
        label={`Enable ${rule.name}`}
        checked={rule.enabled}
        disabled={toggle.isPending}
        onChange={(event) => toggle.mutate(event.target.checked)}
      />
      {/* The state in words: status is never carried by the switch's colour
          alone (WCAG 2.1 AA, US-14.2). */}
      <span className="text-sm text-ink-secondary">{rule.enabled ? 'Active' : 'Inactive'}</span>
    </div>
  )
}
