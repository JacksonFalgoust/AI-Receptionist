import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import {
  ESCALATION_CONDITIONS,
  ROUTING_DESTINATION_TYPES,
  ROUTING_SCHEDULES,
  conditionDetailLabel,
  destinationValueLabel,
  escalationConditionLabel,
  routingDestinationLabel,
  routingScheduleLabel,
} from '@/lib/routingLabels'
import { toAppError } from '@/services/errors'
import { routingService } from '@/services/routingService'
import type { RoutingRule } from '@/types'

import { ROUTING_RULES_KEY } from './RuleStatusToggle'
import {
  formValuesToInput,
  routingRuleFormSchema,
  ruleToFormValues,
} from './routingRuleFormSchema'
import type { RoutingRuleFormValues } from './routingRuleFormSchema'

const CONDITION_OPTIONS = ESCALATION_CONDITIONS.map((condition) => ({
  value: condition,
  label: escalationConditionLabel(condition),
}))
const DESTINATION_OPTIONS = ROUTING_DESTINATION_TYPES.map((type) => ({
  value: type,
  label: routingDestinationLabel(type),
}))
const SCHEDULE_OPTIONS = ROUTING_SCHEDULES.map((schedule) => ({
  value: schedule,
  label: routingScheduleLabel(schedule),
}))

export interface RoutingRuleModalProps {
  isOpen: boolean
  onClose: () => void
  /** Absent means create. */
  rule?: RoutingRule
  /** Where a new rule lands in the evaluation order; ignored when editing. */
  defaultPriority?: number
}

/**
 * US-10.1's add/edit/delete. One modal for both modes — six fields with no
 * sub-collections do not justify a route, and the table stays the single place
 * rules are seen.
 *
 * Two fields follow a sibling's value: the detail field appears only for the
 * conditions that mean nothing without one, and the destination value is
 * labelled for the type chosen.
 */
export function RoutingRuleModal({
  isOpen,
  onClose,
  rule,
  defaultPriority = 1,
}: RoutingRuleModalProps) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const toast = useToast()

  // Tracks whether a confirm() call is in flight, so the modal's own footer
  // can be pulled out of the accessible tree while the confirm dialog's is
  // on top of it — otherwise both have a "Cancel" button and
  // `getByRole('button', { name: /cancel/i })` is ambiguous. Mirrors
  // ManageUserModal's fix for the same bug. Kept mounted rather than
  // conditionally rendered, since unmounting a competing element breaks
  // `useFocusTrap`.
  const [isConfirming, setIsConfirming] = useState(false)

  const form = useForm<RoutingRuleFormValues>({
    resolver: zodResolver(routingRuleFormSchema),
    defaultValues: ruleToFormValues(rule, defaultPriority),
  })
  const { formState, handleSubmit, register, reset, setValue, watch } = form

  // Reopening, or opening on a different rule, reloads the form from that
  // rule rather than leaving the previous one's values behind.
  useEffect(() => {
    if (isOpen) reset(ruleToFormValues(rule, defaultPriority))
  }, [isOpen, rule, defaultPriority, reset])

  const condition = watch('condition')
  const destinationType = watch('destinationType')
  const enabled = watch('enabled')
  const detailLabel = conditionDetailLabel(condition)

  function settle(message: string) {
    void queryClient.invalidateQueries({ queryKey: ROUTING_RULES_KEY })
    toast.show(message, { tone: 'success' })
    onClose()
  }

  const save = useMutation({
    mutationFn: (values: RoutingRuleFormValues) => {
      const input = formValuesToInput(values)
      return rule ? routingService.update(rule.id, input) : routingService.create(input)
    },
    onSuccess: (saved) => settle(rule ? `${saved.name} saved.` : `${saved.name} created.`),
    onError: (error) => toast.show(toAppError(error).description, { tone: 'danger' }),
  })

  const remove = useMutation({
    mutationFn: () => routingService.remove(rule!.id),
    onSuccess: () => settle(`${rule!.name} deleted.`),
    onError: (error) => toast.show(toAppError(error).description, { tone: 'danger' }),
  })

  const isBusy = save.isPending || remove.isPending

  function handleClose() {
    if (isBusy) return
    onClose()
  }

  async function handleDelete() {
    if (!rule) return
    setIsConfirming(true)
    try {
      const confirmed = await confirm({
        title: `Delete ${rule.name}?`,
        description:
          'Escalations that matched this rule will fall through to the next one that applies.',
        confirmLabel: 'Delete',
        tone: 'danger',
      })
      if (!confirmed) return
      remove.mutate()
    } finally {
      setIsConfirming(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={rule ? 'Edit rule' : 'Add rule'}
      actions={
        <div
          className="flex w-full gap-2"
          aria-hidden={isConfirming}
          tabIndex={isConfirming ? -1 : undefined}
        >
          {rule ? (
            <Button
              variant="danger"
              onClick={handleDelete}
              isLoading={remove.isPending}
              className="mr-auto"
            >
              Delete rule
            </Button>
          ) : null}
          <Button variant="ghost" onClick={handleClose} disabled={isBusy}>
            Cancel
          </Button>
          <Button onClick={handleSubmit((values) => save.mutate(values))} isLoading={save.isPending}>
            {rule ? 'Save rule' : 'Create rule'}
          </Button>
        </div>
      }
    >
      <Field label="Rule name" htmlFor="rule-name" error={formState.errors.name?.message}>
        <Input invalid={Boolean(formState.errors.name)} {...register('name')} />
      </Field>

      <Field label="When this happens" htmlFor="rule-condition">
        <Select options={CONDITION_OPTIONS} {...register('condition')} />
      </Field>

      {detailLabel ? (
        <Field
          label={detailLabel}
          htmlFor="rule-condition-detail"
          error={formState.errors.conditionDetail?.message}
        >
          <Input
            invalid={Boolean(formState.errors.conditionDetail)}
            {...register('conditionDetail')}
          />
        </Field>
      ) : null}

      <Field label="Send to" htmlFor="rule-destination-type">
        <Select options={DESTINATION_OPTIONS} {...register('destinationType')} />
      </Field>

      <Field
        label={destinationValueLabel(destinationType)}
        htmlFor="rule-destination-value"
        error={formState.errors.destinationValue?.message}
      >
        <Input
          invalid={Boolean(formState.errors.destinationValue)}
          {...register('destinationValue')}
        />
      </Field>

      <Field label="Applies during" htmlFor="rule-schedule">
        <Select options={SCHEDULE_OPTIONS} {...register('schedule')} />
      </Field>

      <Field
        label="Priority"
        htmlFor="rule-priority"
        description="Lower numbers are checked first. Rules may share a priority."
        error={formState.errors.priority?.message}
      >
        <Input
          type="number"
          min={1}
          invalid={Boolean(formState.errors.priority)}
          {...register('priority', { valueAsNumber: true })}
        />
      </Field>

      <Toggle
        label="Active"
        checked={enabled}
        onChange={(event) => setValue('enabled', event.target.checked)}
      />
    </Modal>
  )
}
