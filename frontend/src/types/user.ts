import type { Id, IsoDateTime, TenantScoped } from './common'

/**
 * PRD §19.2. Declared as a const object + derived union rather than a TS enum
 * because `erasableSyntaxOnly` forbids enums, and this form is also iterable
 * for rendering role pickers.
 */
export const ROLES = [
  'owner',
  'administrator',
  'manager',
  'agent',
  'analyst',
  'viewer',
] as const

export type Role = (typeof ROLES)[number]

export const ROLE_LABELS: Record<Role, string> = {
  owner: 'Owner',
  administrator: 'Administrator',
  manager: 'Manager',
  agent: 'Agent',
  analyst: 'Analyst',
  viewer: 'Viewer',
}

export type UserStatus = 'active' | 'invited' | 'disabled'

export interface User extends TenantScoped {
  id: Id
  name: string
  email: string
  role: Role
  status: UserStatus
  lastLoginAt?: IsoDateTime
}

/** The signed-in principal. Narrower than `User` — no admin-only fields. */
export interface SessionUser {
  id: Id
  name: string
  email: string
  role: Role
  organizationId: Id
  organizationName: string
}

export interface Session {
  token: string
  user: SessionUser
  expiresAt: IsoDateTime
}
