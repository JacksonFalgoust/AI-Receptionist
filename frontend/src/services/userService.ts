import { nextId } from '@/mocks/query'
import { MOCK_ORGANIZATION_ID } from '@/mocks/session'
import { store } from '@/mocks/store'
import type { Id, Role, User, UserStatus } from '@/types'

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
    user.role = role
    return user
  },

  async setStatus(id, status) {
    await delay()
    const user = requireUser(id)
    user.status = status
    return user
  },

  async remove(id) {
    await delay()
    requireUser(id)
    store.users = store.users.filter((user) => user.id !== id)
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
