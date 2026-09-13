import { describe, expect, it } from 'vitest'

import type { User } from '@/types'

import { lastOwnerReason, selfActionReason, userActionReason } from './userGuards'

function user(overrides: Partial<User> & Pick<User, 'id'>): User {
  return {
    organizationId: 'org_horizon',
    name: 'Test Person',
    email: 'test@horizonpartners.example.com',
    role: 'agent',
    status: 'active',
    ...overrides,
  }
}

const ACTIVE_OWNER = user({ id: 'user_owner', name: 'Jordan Lee', role: 'owner' })
const SECOND_OWNER = user({ id: 'user_owner_2', name: 'Avery Chen', role: 'owner' })
const INVITED_OWNER = user({ id: 'user_owner_invited', role: 'owner', status: 'invited' })
const AGENT = user({ id: 'user_agent' })

describe('selfActionReason', () => {
  it('blocks each action on your own row, naming the action', () => {
    expect(selfActionReason('changeRole', AGENT, 'user_agent')).toBe(
      "You can't change your own role.",
    )
    expect(selfActionReason('disable', AGENT, 'user_agent')).toBe(
      "You can't disable your own access.",
    )
    expect(selfActionReason('remove', AGENT, 'user_agent')).toBe(
      "You can't remove your own access.",
    )
  })

  it('allows every action on somebody else', () => {
    expect(selfActionReason('remove', AGENT, 'user_owner')).toBeNull()
  })

  it('allows every action when there is no actor', () => {
    expect(selfActionReason('remove', AGENT, undefined)).toBeNull()
  })
})

describe('lastOwnerReason', () => {
  it('blocks the only active owner, naming the organization', () => {
    expect(lastOwnerReason(ACTIVE_OWNER, [ACTIVE_OWNER, AGENT], 'Horizon Partners')).toBe(
      'Horizon Partners needs at least one Owner.',
    )
  })

  it('allows an owner while another active owner remains', () => {
    expect(
      lastOwnerReason(ACTIVE_OWNER, [ACTIVE_OWNER, SECOND_OWNER, AGENT], 'Horizon Partners'),
    ).toBeNull()
  })

  it('ignores non-owners entirely', () => {
    expect(lastOwnerReason(AGENT, [ACTIVE_OWNER, AGENT], 'Horizon Partners')).toBeNull()
  })

  // An owner who has never signed in cannot hold the organization, so removing
  // them cannot be what strands it — and guarding them would make a mistaken
  // owner invitation impossible to revoke.
  it('allows an invited owner to be removed even with no other owner', () => {
    expect(lastOwnerReason(INVITED_OWNER, [INVITED_OWNER, AGENT], 'Horizon Partners')).toBeNull()
  })

  it('does not count an invited owner as the one that keeps the organization safe', () => {
    expect(
      lastOwnerReason(ACTIVE_OWNER, [ACTIVE_OWNER, INVITED_OWNER], 'Horizon Partners'),
    ).toBe('Horizon Partners needs at least one Owner.')
  })

  it('does not count a disabled owner either', () => {
    const disabledOwner = user({ id: 'user_owner_off', role: 'owner', status: 'disabled' })
    expect(lastOwnerReason(ACTIVE_OWNER, [ACTIVE_OWNER, disabledOwner], 'Horizon Partners')).toBe(
      'Horizon Partners needs at least one Owner.',
    )
  })
})

describe('userActionReason', () => {
  const context = {
    actorId: 'user_owner',
    organizationName: 'Horizon Partners',
    users: [ACTIVE_OWNER, AGENT],
  }

  it('reports the self reason ahead of the owner reason', () => {
    expect(userActionReason('remove', ACTIVE_OWNER, context)).toBe(
      "You can't remove your own access.",
    )
  })

  it('reports the owner reason when the actor is somebody else', () => {
    expect(
      userActionReason('remove', ACTIVE_OWNER, { ...context, actorId: 'user_administrator' }),
    ).toBe('Horizon Partners needs at least one Owner.')
  })

  it('returns null when nothing blocks the action', () => {
    expect(userActionReason('remove', AGENT, context)).toBeNull()
  })
})
