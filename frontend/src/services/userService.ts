import { lastOwnerReason, selfActionReason } from '@/lib/userGuards'
import { nextId } from '@/mocks/query'
import { MOCK_ORGANIZATION_ID } from '@/mocks/session'
import { store } from '@/mocks/store'
import type { Id, Role, User, UserStatus } from '@/types'

import { authService } from './authService'
import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

export interface InviteUserInput {
  name: string
  email: string
  role: Role
}

/** PRD §19 / US-11.1. */
export interface UserService {
  list(): Promise<User[]>
  invite(input: InviteUserInput): Promise<User>
  updateRole(id: Id, role: Role): Promise<User>
  setStatus(id: Id, status: UserStatus): Promise<User>
  remove(id: Id): Promise<void>
  resendInvitation(id: Id): Promise<void>
}

function requireUser(id: Id): User {
  const user = store.users.find((item) => item.id === id)
  if (!user) {
    throw new AppError({
      kind: 'not_found',
      title: 'User not found',
      description: 'That person is no longer part of this organization.',
      actions: [{ label: 'Back to users', href: '/admin/users' }],
    })
  }
  return user
}

/**
 * The actor, read from the same persisted session the app treats as its
 * identity. Deliberately not a parameter on the service interface: a real API
 * reads the actor from the bearer token and would never take it as an
 * argument, so an `actorId` parameter would be a permanent lie in the contract
 * that E6 then has to strip out.
 *
 * Undefined in a unit test that seeds no session, where self-protection is
 * simply skipped — the last-owner rule needs no actor and still applies.
 */
function actor(): { id: Id; organizationName: string } | undefined {
  const session = authService.getStoredSession()
  if (!session) return undefined
  return { id: session.user.id, organizationName: session.user.organizationName }
}

function organizationName(): string {
  return actor()?.organizationName ?? 'Your organization'
}

/**
 * IMPORTANT (PRD §40): these guards run client-side against an in-memory
 * store. The real API must enforce both rules independently before E6 ships.
 */
function guard(reason: string | null): void {
  if (!reason) return
  throw new AppError({
    kind: 'validation',
    title: 'That change is not allowed',
    description: reason,
  })
}

const mockUserService: UserService = {
  async list() {
    await delay()
    return [...store.users]
  },

  async invite(input) {
    await delay()
    const email = input.email.trim().toLowerCase()

    if (store.users.some((user) => user.email.toLowerCase() === email)) {
      throw new AppError({
        kind: 'validation',
        title: 'That person is already on your team',
        description: 'Choose a different email address, or edit their existing role.',
        // Keyed so the invite form can highlight the offending field directly.
        fieldErrors: { email: 'This email address already has access.' },
      })
    }

    const user: User = {
      id: nextId('user'),
      organizationId: MOCK_ORGANIZATION_ID,
      name: input.name,
      email: input.email,
      role: input.role,
      status: 'invited',
    }
    store.users.push(user)
    return user
  },

  async updateRole(id, role) {
    await delay()
    const user = requireUser(id)
    guard(selfActionReason('changeRole', user, actor()?.id))
    // Promoting someone to Owner — or re-setting an owner to Owner — can never
    // leave the organization without one, so only a move away is guarded.
    if (role !== 'owner') {
      guard(lastOwnerReason(user, store.users, organizationName()))
    }
    user.role = role
    return user
  },

  async setStatus(id, status) {
    await delay()
    const user = requireUser(id)
    if (status === 'disabled') {
      guard(selfActionReason('disable', user, actor()?.id))
      guard(lastOwnerReason(user, store.users, organizationName()))
    }
    user.status = status
    return user
  },

  async remove(id) {
    await delay()
    const user = requireUser(id)
    guard(selfActionReason('remove', user, actor()?.id))
    guard(lastOwnerReason(user, store.users, organizationName()))
    store.users = store.users.filter((item) => item.id !== id)
  },

  async resendInvitation(id) {
    await delay()
    const user = requireUser(id)
    if (user.status !== 'invited') {
      throw new AppError({
        kind: 'validation',
        title: 'There is no pending invitation',
        description: `${user.name} has already accepted their invitation.`,
      })
    }
  },
}

const httpUserService: UserService = {
  list: () => http.get<User[]>('/users'),
  invite: (input) => http.post<User>('/users/invite', input),
  updateRole: (id, role) => http.patch<User>(`/users/${id}/role`, { role }),
  setStatus: (id, status) => http.patch<User>(`/users/${id}/status`, { status }),
  remove: (id) => http.delete<void>(`/users/${id}`),
  resendInvitation: (id) => http.post<void>(`/users/${id}/resend-invitation`),
}

export const userService: UserService = USE_MOCKS ? mockUserService : httpUserService
