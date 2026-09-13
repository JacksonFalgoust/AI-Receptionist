import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { useToast } from '@/components/ui/ToastProvider'
import { toAppError } from '@/services/errors'
import { userService } from '@/services/userService'
import { ROLE_LABELS, ROLES } from '@/types'

import { INVITE_DEFAULTS, inviteUserFormSchema } from './inviteUserFormSchema'
import type { InviteUserFormValues } from './inviteUserFormSchema'
import { USERS_KEY } from './usersQuery'

const ROLE_OPTIONS = ROLES.map((role) => ({ value: role, label: ROLE_LABELS[role] }))

export interface InviteUserModalProps {
  isOpen: boolean
  onClose: () => void
}

/** US-11.1's Invite action. */
export function InviteUserModal({ isOpen, onClose }: InviteUserModalProps) {
  const queryClient = useQueryClient()
  const toast = useToast()

  const { formState, handleSubmit, register, reset, setError } = useForm<InviteUserFormValues>({
    resolver: zodResolver(inviteUserFormSchema),
    defaultValues: INVITE_DEFAULTS,
  })

  // Reopening starts blank rather than showing the last person invited.
  useEffect(() => {
    if (isOpen) reset(INVITE_DEFAULTS)
  }, [isOpen, reset])

  const invite = useMutation({
    mutationFn: (values: InviteUserFormValues) => userService.invite(values),
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: USERS_KEY })
      toast.show(`Invitation sent to ${user.email}.`, { tone: 'success' })
      onClose()
    },
    onError: (error) => {
      const appError = toAppError(error)
      // A6 keyed the duplicate-email failure to a field for exactly this.
      // Nothing had consumed `fieldErrors` before now.
      const fieldErrors = appError.fieldErrors
      if (fieldErrors) {
        for (const [field, message] of Object.entries(fieldErrors)) {
          setError(field as keyof InviteUserFormValues, { message })
        }
        return
      }
      toast.show(appError.description, { tone: 'danger' })
    },
  })

  function handleClose() {
    if (invite.isPending) return
    onClose()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Invite user"
      actions={
        <>
          <Button variant="ghost" onClick={handleClose} disabled={invite.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit((values) => invite.mutate(values))}
            isLoading={invite.isPending}
          >
            Send invitation
          </Button>
        </>
      }
    >
      <Field label="Full name" htmlFor="invite-name" error={formState.errors.name?.message}>
        <Input invalid={Boolean(formState.errors.name)} {...register('name')} />
      </Field>

      <Field label="Email address" htmlFor="invite-email" error={formState.errors.email?.message}>
        <Input type="email" invalid={Boolean(formState.errors.email)} {...register('email')} />
      </Field>

      <Field
        label="Role"
        htmlFor="invite-role"
        description="Sets what this person can see and change. You can change it later."
      >
        <Select options={ROLE_OPTIONS} {...register('role')} />
      </Field>
    </Modal>
  )
}
