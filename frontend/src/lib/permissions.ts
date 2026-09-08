import type { Role } from '@/types'

/**
 * Capability-based access, derived from the user types in PRD §4.
 *
 * IMPORTANT (PRD §40): this drives navigation and route guards only. Hiding a
 * control is not security — the backend must enforce every one of these
 * independently before the corresponding API ships.
 */
export const PERMISSIONS = [
  'view:overview',
  'view:conversations',
  'view:activity',
  'view:analytics',
  'manage:configuration',
  'manage:features',
  'manage:workflows',
  'manage:knowledge',
  'manage:integrations',
  'manage:routing',
  'manage:users',
  'view:security',
  'manage:billing',
  'use:test',
] as const

export type Permission = (typeof PERMISSIONS)[number]

const ALL: Permission[] = [...PERMISSIONS]

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  owner: ALL,
  administrator: ALL,
  // PRD §4.2: operational reach, but not billing, user admin, or security.
  manager: [
    'view:overview',
    'view:conversations',
    'view:activity',
    'view:analytics',
    'manage:routing',
    'use:test',
  ],
  // PRD §4.3: works assigned escalations and the conversations behind them.
  agent: ['view:overview', 'view:conversations', 'view:activity'],
  // PRD §4.4: reporting only, no configuration.
  analyst: ['view:overview', 'view:analytics'],
  // PRD §4.5: read-only.
  viewer: ['view:overview', 'view:conversations', 'view:analytics'],
}

export function can(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].includes(permission)
}

export function canAny(role: Role, permissions: Permission[]): boolean {
  return permissions.some((permission) => can(role, permission))
}
