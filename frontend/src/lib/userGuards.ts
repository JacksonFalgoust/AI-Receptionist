import type { Id, User } from '@/types'

/**
 * The three actions that can take access away from someone. Inviting and
 * restoring access are unguarded — they grant rather than remove, and neither
 * can strand the organization.
 *
 * Pure and dependency-free so both sides can share one source of truth:
 * `ManageUserModal` renders the reason beside a disabled control, and
 * `userService` throws the same sentence as a validation error.
 *
 * IMPORTANT (PRD §40): the service-side check is a mock. The real API must
 * enforce both of these rules server-side before E6 ships — a disabled button
 * is not security, and neither is a mock that throws.
 */
export type GuardedUserAction = 'changeRole' | 'disable' | 'remove'

export interface GuardContext {
  /** The signed-in user's id. Undefined outside a session, e.g. in a unit test. */
  actorId?: Id
  /** Named in the last-owner message, the way D2's disconnect dialog names features. */
  organizationName: string
  /** Everyone in the organization, used to count the owners who remain. */
  users: User[]
}

const SELF_REASONS: Record<GuardedUserAction, string> = {
  changeRole: "You can't change your own role.",
  disable: "You can't disable your own access.",
  remove: "You can't remove your own access.",
}

/** Why the signed-in user may not do this to themselves. */
export function selfActionReason(
  action: GuardedUserAction,
  target: User,
  actorId?: Id,
): string | null {
  if (!actorId || target.id !== actorId) return null
  return SELF_REASONS[action]
}

/**
 * Why this person may not lose the Owner role, be disabled, or be removed.
 *
 * The invariant is "at least one *active* Owner". Only an active owner's
 * departure can violate it: an owner who is invited or disabled cannot sign in,
 * so they are never what is holding the organization together — and guarding
 * them would make a mistaken owner invitation impossible to revoke.
 */
export function lastOwnerReason(
  target: User,
  users: User[],
  organizationName: string,
): string | null {
  if (target.role !== 'owner' || target.status !== 'active') return null

  const otherActiveOwners = users.filter(
    (user) => user.id !== target.id && user.role === 'owner' && user.status === 'active',
  )
  if (otherActiveOwners.length > 0) return null

  return `${organizationName} needs at least one Owner.`
}

/**
 * Both rules at once, for the UI. Self-protection is reported first: it is the
 * more specific answer when both apply, and "you can't remove your own access"
 * is more actionable than a rule about the organization.
 */
export function userActionReason(
  action: GuardedUserAction,
  target: User,
  context: GuardContext,
): string | null {
  return (
    selfActionReason(action, target, context.actorId) ??
    lastOwnerReason(target, context.users, context.organizationName)
  )
}
