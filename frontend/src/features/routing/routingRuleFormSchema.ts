import { z } from 'zod'

import {
  ESCALATION_CONDITIONS,
  ROUTING_DESTINATION_TYPES,
  ROUTING_SCHEDULES,
  conditionDetailLabel,
} from '@/lib/routingLabels'
import type { CreateRoutingRuleInput } from '@/services/routingService'
import type {
  EscalationCondition,
  RoutingDestinationType,
  RoutingSchedule,
  RoutingRule,
} from '@/types'

/**
 * `RoutingRule` laid out flat, as the form's controls read it — the nested
 * `destination` is split into two fields and put back together on submit.
 */
export interface RoutingRuleFormValues {
  name: string
  condition: EscalationCondition
  /** `''` when the condition takes no detail. */
  conditionDetail: string
  destinationType: RoutingDestinationType
  destinationValue: string
  schedule: RoutingSchedule
  priority: number
  enabled: boolean
}

// The derived label arrays are `Union[]`, while `z.enum` wants a non-empty
// tuple. The records they come from are non-empty by construction, so the
// assertion is safe and keeps `routingLabels.ts` matching its sibling
// `integrationLabels.ts` exactly.
const conditions = ESCALATION_CONDITIONS as [EscalationCondition, ...EscalationCondition[]]
const destinationTypes = ROUTING_DESTINATION_TYPES as [
  RoutingDestinationType,
  ...RoutingDestinationType[],
]
const schedules = ROUTING_SCHEDULES as [RoutingSchedule, ...RoutingSchedule[]]

export const routingRuleFormSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter a rule name'),
    condition: z.enum(conditions),
    conditionDetail: z.string(),
    destinationType: z.enum(destinationTypes),
    destinationValue: z.string().trim().min(1, 'Enter where escalations should go'),
    schedule: z.enum(schedules),
    // A cleared number input parses to NaN, which fails `.int()` and surfaces
    // as this message rather than passing through as a blank priority.
    priority: z
      .number({ message: 'Enter a priority' })
      .int('Priority must be a whole number')
      .min(1, 'Priority starts at 1'),
    enabled: z.boolean(),
  })
  .superRefine((values, ctx) => {
    const detailLabel = conditionDetailLabel(values.condition)
    if (detailLabel && values.conditionDetail.trim() === '') {
      ctx.addIssue({
        code: 'custom',
        path: ['conditionDetail'],
        message: `Enter the ${detailLabel.toLowerCase()} this rule matches`,
      })
    }
  })

/**
 * An existing rule as form values, or a blank rule at `defaultPriority`. A new
 * rule starts enabled: an admin adding a rule means it to route something.
 */
export function ruleToFormValues(rule?: RoutingRule, defaultPriority = 1): RoutingRuleFormValues {
  if (!rule) {
    return {
      name: '',
      condition: ESCALATION_CONDITIONS[0],
      conditionDetail: '',
      destinationType: ROUTING_DESTINATION_TYPES[0],
      destinationValue: '',
      schedule: ROUTING_SCHEDULES[0],
      priority: defaultPriority,
      enabled: true,
    }
  }

  return {
    name: rule.name,
    condition: rule.condition,
    conditionDetail: rule.conditionDetail ?? '',
    destinationType: rule.destination.type,
    destinationValue: rule.destination.value,
    schedule: rule.schedule,
    priority: rule.priority,
    enabled: rule.enabled,
  }
}

/** The submitted form, turned into what `routingService.create`/`update` expect. */
export function formValuesToInput(values: RoutingRuleFormValues): CreateRoutingRuleInput {
  // A detail typed under one condition must not survive a switch to a
  // condition that takes none — it would be stored, invisible, and outlive
  // the reason it was entered.
  const keepsDetail = Boolean(conditionDetailLabel(values.condition))
  const detail = values.conditionDetail.trim()

  return {
    name: values.name.trim(),
    condition: values.condition,
    conditionDetail: keepsDetail && detail !== '' ? detail : undefined,
    destination: { type: values.destinationType, value: values.destinationValue.trim() },
    schedule: values.schedule,
    priority: values.priority,
    enabled: values.enabled,
  }
}
