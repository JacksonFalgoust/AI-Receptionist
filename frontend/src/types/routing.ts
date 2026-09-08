import type { Id, TenantScoped } from './common'

/** PRD §18.1 */
export type EscalationCondition =
  | 'customer_requests_person'
  | 'cannot_answer'
  | 'frustration_detected'
  | 'complaint'
  | 'refund_requested'
  | 'transaction_over_threshold'
  | 'vip_customer'
  | 'keyword_match'
  | 'workflow_failure'
  | 'integration_unavailable'

/** PRD §18.2 */
export type RoutingDestinationType =
  | 'employee'
  | 'team'
  | 'department'
  | 'queue'
  | 'phone_number'
  | 'external_system'

export interface RoutingDestination {
  type: RoutingDestinationType
  /** Display name or number, e.g. "Sam Rivera" or "+1 555 0142". */
  value: string
}

/** PRD §18.3 */
export type RoutingSchedule =
  | 'always'
  | 'open_hours'
  | 'after_hours'
  | 'weekends'
  | 'holidays'

export interface RoutingRule extends TenantScoped {
  id: Id
  name: string
  condition: EscalationCondition
  /** Free-text detail for conditions that need one, e.g. keyword lists. */
  conditionDetail?: string
  destination: RoutingDestination
  schedule: RoutingSchedule
  /** Lower number wins when several rules match. */
  priority: number
  enabled: boolean
}
