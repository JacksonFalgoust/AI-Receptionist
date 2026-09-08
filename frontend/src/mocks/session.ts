import type { Role, SessionUser } from '@/types'
import { ROLES } from '@/types'

/**
 * Sample tenant used throughout the mock services. "Horizon Partners" is the
 * industry-neutral organization the user stories call for — deliberately not a
 * rental/hospitality/healthcare name (PRD §53.9).
 */
export const MOCK_ORGANIZATION_ID = 'org_horizon'
export const MOCK_ORGANIZATION_NAME = 'Horizon Partners'

/** The password every mock account accepts. Documented in the frontend README. */
export const MOCK_PASSWORD = 'concierge'

/**
 * Lets the signed-in role be chosen from the email local-part
 * (`manager@horizonpartners.com` signs in as a Manager), so role-based
 * navigation can be exercised before a real identity provider exists.
 * Anything unrecognised signs in as Owner.
 */
export function roleForEmail(email: string): Role {
  const localPart = email.split('@')[0]?.toLowerCase() ?? ''
  const match = ROLES.find((role) => role === localPart)
  return match ?? 'owner'
}

export function buildMockSessionUser(email: string): SessionUser {
  const role = roleForEmail(email)
  return {
    id: `user_${role}`,
    name: role === 'owner' ? 'Jordan Lee' : nameForRole(role),
    email,
    role,
    organizationId: MOCK_ORGANIZATION_ID,
    organizationName: MOCK_ORGANIZATION_NAME,
  }
}

function nameForRole(role: Role): string {
  const names: Record<Role, string> = {
    owner: 'Jordan Lee',
    administrator: 'Avery Chen',
    manager: 'Sam Rivera',
    agent: 'Taylor Brooks',
    analyst: 'Priya Shah',
    viewer: 'Chris Nguyen',
  }
  return names[role]
}
