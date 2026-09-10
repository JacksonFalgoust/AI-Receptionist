import type { ReactNode } from 'react'

import { Table } from '@/components/ui/Table'
import type { TableColumn } from '@/components/ui/Table'
import {
  escalationConditionLabel,
  routingDestinationLabel,
  routingScheduleLabel,
} from '@/lib/routingLabels'
import type { RoutingRule } from '@/types'

import { RuleStatusToggle } from './RuleStatusToggle'

export interface RoutingRulesTableProps {
  rules: RoutingRule[]
  /** D4's Edit action. Omitted, the table is read-only. */
  renderRowAction?: (rule: RoutingRule) => ReactNode
}

/**
 * PRD §18.4's six columns. Presentational: the only mutation on the screen
 * lives inside `RuleStatusToggle`.
 *
 * No filters and no pagination — neither the PRD nor `routing.html` calls for
 * either at this row count, the same call C6 made for the workflow list.
 * `routingService.list()` already sorts priority-ascending, so rows arrive in
 * the order the rules are actually evaluated.
 */
export function RoutingRulesTable({ rules, renderRowAction }: RoutingRulesTableProps) {
  const columns: TableColumn<RoutingRule>[] = [
    {
      id: 'name',
      header: 'Rule',
      render: (rule) => <span className="font-medium text-ink">{rule.name}</span>,
      sortValue: (rule) => rule.name,
    },
    {
      id: 'condition',
      header: 'Condition',
      render: (rule) => (
        <div>
          <p>{escalationConditionLabel(rule.condition)}</p>
          {/* Without this, the threshold rule shows no amount and the keyword
              rule shows no keywords. */}
          {rule.conditionDetail ? (
            <p className="text-xs text-ink-muted">{rule.conditionDetail}</p>
          ) : null}
        </div>
      ),
      sortValue: (rule) => escalationConditionLabel(rule.condition),
    },
    {
      id: 'destination',
      header: 'Destination',
      render: (rule) => (
        <div>
          <p>{rule.destination.value}</p>
          <p className="text-xs text-ink-muted">
            {routingDestinationLabel(rule.destination.type)}
          </p>
        </div>
      ),
      sortValue: (rule) => rule.destination.value,
    },
    {
      id: 'schedule',
      header: 'Schedule',
      render: (rule) => routingScheduleLabel(rule.schedule),
      sortValue: (rule) => routingScheduleLabel(rule.schedule),
    },
    {
      id: 'priority',
      header: 'Priority',
      render: (rule) => rule.priority,
      sortValue: (rule) => rule.priority,
    },
    {
      id: 'status',
      header: 'Status',
      render: (rule) => <RuleStatusToggle rule={rule} />,
      sortValue: (rule) => (rule.enabled ? 'Active' : 'Inactive'),
    },
  ]

  if (renderRowAction) {
    columns.push({
      id: 'actions',
      header: '',
      render: (rule) => renderRowAction(rule),
    })
  }

  return <Table columns={columns} rows={rules} getRowId={(rule) => rule.id} frame={false} />
}
