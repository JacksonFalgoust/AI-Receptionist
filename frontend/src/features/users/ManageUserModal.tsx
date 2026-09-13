import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { useToast } from '@/components/ui/ToastProvider'
import { useConfirm } from '@/components/ui/useConfirm'
import { useAuth } from '@/features/auth/useAuth'
import { userActionReason } from '@/lib/userGuards'
import { toAppError } from '@/services/errors'
import { userService } from '@/services/userService'
import { ROLE_LABELS, ROLES } from '@/types'
import type { Role, User } from '@/types'

import { USERS_KEY } from './usersQuery'

const ROLE_OPTIONS = ROLES.map((role) => ({ value: role, label: ROLE_LABELS[role] }))

export interface ManageUserModalProps {
  isOpen: boolean
  onClose: () => void
  /** Null closes the modal — the page clears it to dismiss. */
  user: User | null
  /** Everyone in the organization, so the last-owner rule can be evaluated. */
  users: User[]
}

/**
 * US-11.1's four per-row actions in one modal, mirroring `RoutingRuleModal`'s
 * structure: the form field at the top, the destructive action `mr-auto` in the
 * footer, Cancel and the primary action on the right.
 *
 * Chosen over a per-row kebab `Dropdown` because `Table` wraps its rows in
 * `overflow-x-auto`, which clips an absolutely-positioned dropdown panel on the
 * last rows. Avoiding that would mean portalling `Dropdown`, a change to a
 * shared primitive the header panels already depend on.
 */
export function ManageUserModal({ isOpen, onClose, user, users }: ManageUserModalProps) {
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const toast = useToast()
  const { user: signedIn } = useAuth()

  const [role, setRole] = useState<Role>(user?.role ?? 'viewer')
  // Tracks whether a confirm() call is in flight, so the outer modal's own
  // footer can be pulled out of the accessible tree while the confirm
  // dialog's is on top of it — otherwise both have a "Cancel" button and
  // `getByRole('button', { name: /cancel/i })` is ambiguous (the same class
  // of collision D2 hit with Remove/Remove user). Kept mounted rather than
  // conditionally rendered: D2 also learned that unmounting a competing
  // element breaks `useFocusTrap`, which captures `document.activeElement`
  // on open and calls `.focus()` on that same node on close.
  const [isConfirming, setIsConfirming] = useState(false)

  // Opening on a different person loads that person's role rather than
  // leaving the previous selection behind.
  useEffect(() => {
    if (isOpen && user) setRole(user.role)
  }, [isOpen, user])

  const guardContext = {
    actorId: signedIn?.id,
    organizationName: signedIn?.organizationName ?? 'Your organization',
    users,
  }

  function settle(message: string) {
    void queryClient.invalidateQueries({ queryKey: USERS_KEY })
    toast.show(message, { tone: 'success' })
    onClose()
  }

  function fail(error: unknown) {
    toast.show(toAppError(error).description, { tone: 'danger' })
  }

  const saveRole = useMutation({
    mutationFn: () => userService.updateRole(user!.id, role),
    onSuccess: (updated) => settle(`${updated.name} is now ${ROLE_LABELS[updated.role]}.`),
    onError: fail,
  })

  const resend = useMutation({
    mutationFn: () => userService.resendInvitation(user!.id),
    onSuccess: () => settle(`Invitation resent to ${user!.email}.`),
    onError: fail,
  })

  const setStatus = useMutation({
    mutationFn: (next: 'active' | 'disabled') => userService.setStatus(user!.id, next),
    onSuccess: (updated) =>
      settle(
        updated.status === 'disabled'
          ? `${updated.name} no longer has access.`
          : `${updated.name} has access again.`,
      ),
    onError: fail,
  })

  const remove = useMutation({
    mutationFn: () => userService.remove(user!.id),
    onSuccess: () => settle(`${user!.name} was removed from the organization.`),
    onError: fail,
  })

  if (!user) return null

  const isBusy =
    saveRole.isPending || resend.isPending || setStatus.isPending || remove.isPending

  const roleReason = userActionReason('changeRole', user, guardContext)
  const disableReason = userActionReason('disable', user, guardContext)
  const removeReason = userActionReason('remove', user, guardContext)

  function handleClose() {
    if (isBusy) return
    onClose()
  }

  async function handleDisable() {
    setIsConfirming(true)
    try {
      const confirmed = await confirm({
        title: `Disable ${user!.name}?`,
        description: `${user!.name} will lose access to ${guardContext.organizationName} until you restore it.`,
        confirmLabel: 'Disable',
        tone: 'danger',
      })
      if (confirmed) setStatus.mutate('disabled')
    } finally {
      setIsConfirming(false)
    }
  }

  async function handleRemove() {
    setIsConfirming(true)
    try {
      const confirmed = await confirm({
        title: `Remove ${user!.name}?`,
        // Names the consequence concretely rather than generically, the way
        // D2's disconnect dialog names the features that stop working.
        description: `${user!.name} will lose access to ${guardContext.organizationName} immediately. This cannot be undone.`,
        confirmLabel: 'Remove user',
        tone: 'danger',
      })
      if (confirmed) remove.mutate()
    } finally {
      setIsConfirming(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`Manage ${user.name}`}
      actions={
        // Pulled out of the accessible tree (not unmounted — see the
        // `isConfirming` comment above) while a confirm dialog from this
        // modal is open on top of it, so its own "Cancel" stops competing
        // with the confirm dialog's.
        <div
          className="flex w-full gap-2"
          aria-hidden={isConfirming}
          tabIndex={isConfirming ? -1 : undefined}
        >
          <Button
            variant="danger"
            className="mr-auto"
            onClick={handleRemove}
            disabled={isBusy || Boolean(removeReason)}
            isLoading={remove.isPending}
          >
            Remove
          </Button>
          <Button variant="ghost" onClick={handleClose} disabled={isBusy}>
            Cancel
          </Button>
          <Button
            onClick={() => saveRole.mutate()}
            disabled={isBusy || Boolean(roleReason)}
            isLoading={saveRole.isPending}
          >
            Save role
          </Button>
        </div>
      }
    >
      <p className="mb-4 text-sm text-ink-secondary">{user.email}</p>

      <Field
        label="Role"
        htmlFor="manage-role"
        // The rule is stated rather than hidden: a disabled control with a
        // sentence teaches it, a missing control leaves the admin hunting.
        description={roleReason ?? 'Sets what this person can see and change.'}
      >
        <Select
          options={ROLE_OPTIONS}
          value={role}
          disabled={isBusy || Boolean(roleReason)}
          onChange={(event) => setRole(event.target.value as Role)}
        />
      </Field>

      {user.status === 'invited' ? (
        <div className="mb-4 border-t border-border pt-4">
          <p className="text-sm font-semibold text-ink">Invitation</p>
          <p className="mt-1 mb-2 text-sm text-ink-secondary">Invited — not yet accepted.</p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => resend.mutate()}
            disabled={isBusy}
            isLoading={resend.isPending}
          >
            Resend invitation
          </Button>
        </div>
      ) : null}

      <div className="border-t border-border pt-4">
        <p className="text-sm font-semibold text-ink">Access</p>
        {user.status === 'disabled' ? (
          <>
            <p className="mt-1 mb-2 text-sm text-ink-secondary">
              This person cannot sign in.
            </p>
            {/* Restoring access grants rather than removes, so it is not
                confirmed (PRD §28 lists only Disable and Remove). */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setStatus.mutate('active')}
              disabled={isBusy}
              isLoading={setStatus.isPending}
            >
              Restore access
            </Button>
          </>
        ) : (
          <>
            <p className="mt-1 mb-2 text-sm text-ink-secondary">
              {disableReason ?? 'Keeps the account, but blocks sign-in until you restore it.'}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDisable}
              disabled={isBusy || Boolean(disableReason)}
              isLoading={setStatus.isPending}
            >
              Disable access
            </Button>
          </>
        )}
        {removeReason ? (
          <p className="mt-3 text-xs text-ink-muted">{removeReason}</p>
        ) : null}
      </div>
    </Modal>
  )
}
