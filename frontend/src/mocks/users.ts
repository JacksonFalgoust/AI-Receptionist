import type { User } from '@/types'

import { MOCK_ORGANIZATION_ID } from './session'

const NOW = Date.now()
const HOUR = 60 * 60 * 1000

function isoHoursAgo(hours: number): string {
  return new Date(NOW - hours * HOUR).toISOString()
}

/**
 * All six roles, plus the `invited` and `disabled` statuses (US-11.1).
 * The base array is annotated so `.map()` does not widen `role` and `status`.
 */
const USERS: Omit<User, 'organizationId'>[] = [
  { id: 'user_owner', name: 'Jordan Lee', email: 'owner@horizonpartners.example.com', role: 'owner', status: 'active', lastLoginAt: isoHoursAgo(1) },
  { id: 'user_administrator', name: 'Avery Chen', email: 'administrator@horizonpartners.example.com', role: 'administrator', status: 'active', lastLoginAt: isoHoursAgo(5) },
  { id: 'user_manager', name: 'Sam Rivera', email: 'manager@horizonpartners.example.com', role: 'manager', status: 'active', lastLoginAt: isoHoursAgo(21) },
  { id: 'user_agent', name: 'Taylor Brooks', email: 'agent@horizonpartners.example.com', role: 'agent', status: 'active', lastLoginAt: isoHoursAgo(3) },
  { id: 'user_analyst', name: 'Priya Shah', email: 'analyst@horizonpartners.example.com', role: 'analyst', status: 'active', lastLoginAt: isoHoursAgo(52) },
  { id: 'user_viewer', name: 'Chris Nguyen', email: 'viewer@horizonpartners.example.com', role: 'viewer', status: 'active', lastLoginAt: isoHoursAgo(96) },
  { id: 'user_invited_manager', name: 'Robin Alvarez', email: 'robin.alvarez@horizonpartners.example.com', role: 'manager', status: 'invited' },
  { id: 'user_invited_agent', name: 'Jamie Okafor', email: 'jamie.okafor@horizonpartners.example.com', role: 'agent', status: 'invited' },
  { id: 'user_disabled', name: 'Morgan Vance', email: 'morgan.vance@horizonpartners.example.com', role: 'agent', status: 'disabled', lastLoginAt: isoHoursAgo(2160) },
]

export const userSeed: User[] = USERS.map((user) => ({
  ...user,
  organizationId: MOCK_ORGANIZATION_ID,
}))
