import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'
import { seedSession } from '@/test/renderWithProviders'

import { userService } from './userService'

describe('userService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('lists every user across all six roles', async () => {
    const users = await userService.list()
    expect(new Set(users.map((user) => user.role)).size).toBe(6)
  })

  it('invites a user in the invited status with no last login', async () => {
    const invited = await userService.invite({
      name: 'Casey Lin',
      email: 'casey.lin@horizonpartners.example.com',
      role: 'analyst',
    })

    expect(invited.status).toBe('invited')
    expect(invited.lastLoginAt).toBeUndefined()
    expect((await userService.list()).some((user) => user.id === invited.id)).toBe(true)
  })

  it('rejects an invite for an email already on the team, with a field error', async () => {
    await expect(
      userService.invite({
        name: 'Duplicate Person',
        email: 'manager@horizonpartners.example.com',
        role: 'viewer',
      }),
    ).rejects.toMatchObject({
      kind: 'validation',
      fieldErrors: { email: expect.stringContaining('already') },
    })
  })

  it('matches an existing email case-insensitively', async () => {
    await expect(
      userService.invite({
        name: 'Duplicate Person',
        email: 'MANAGER@horizonpartners.example.com',
        role: 'viewer',
      }),
    ).rejects.toMatchObject({ kind: 'validation' })
  })

  it('updates a role', async () => {
    const updated = await userService.updateRole('user_viewer', 'analyst')
    expect(updated.role).toBe('analyst')
  })

  it('disables and re-enables a user', async () => {
    expect((await userService.setStatus('user_agent', 'disabled')).status).toBe('disabled')
    expect((await userService.setStatus('user_agent', 'active')).status).toBe('active')
  })

  it('removes a user', async () => {
    await userService.remove('user_disabled')
    expect((await userService.list()).some((user) => user.id === 'user_disabled')).toBe(false)
  })

  it('resends an invitation only to an invited user', async () => {
    await expect(userService.resendInvitation('user_invited_agent')).resolves.toBeUndefined()
    await expect(userService.resendInvitation('user_owner')).rejects.toMatchObject({
      kind: 'validation',
    })
  })

  describe('lockout guards', () => {
    it('refuses to remove the signed-in user', async () => {
      seedSession('owner@horizonpartners.example.com')
      await expect(userService.remove('user_owner')).rejects.toMatchObject({
        kind: 'validation',
        description: "You can't remove your own access.",
      })
      expect((await userService.list()).some((user) => user.id === 'user_owner')).toBe(true)
    })

    it('refuses to disable the signed-in user', async () => {
      seedSession('administrator@horizonpartners.example.com')
      await expect(
        userService.setStatus('user_administrator', 'disabled'),
      ).rejects.toMatchObject({ description: "You can't disable your own access." })
    })

    it('refuses to change the signed-in user own role', async () => {
      seedSession('administrator@horizonpartners.example.com')
      await expect(userService.updateRole('user_administrator', 'viewer')).rejects.toMatchObject({
        description: "You can't change your own role.",
      })
    })

    it('refuses to demote the only active owner, naming the organization', async () => {
      seedSession('administrator@horizonpartners.example.com')
      await expect(userService.updateRole('user_owner', 'manager')).rejects.toMatchObject({
        kind: 'validation',
        description: 'Horizon Partners needs at least one Owner.',
      })
    })

    it('refuses to disable or remove the only active owner', async () => {
      seedSession('administrator@horizonpartners.example.com')
      await expect(userService.setStatus('user_owner', 'disabled')).rejects.toMatchObject({
        description: 'Horizon Partners needs at least one Owner.',
      })
      await expect(userService.remove('user_owner')).rejects.toMatchObject({
        description: 'Horizon Partners needs at least one Owner.',
      })
    })

    // Setting the role it already has is a no-op, not a demotion. Guarding it
    // would make the only owner unsaveable from a form that always submits.
    it('allows setting the only owner role to Owner again', async () => {
      seedSession('administrator@horizonpartners.example.com')
      await expect(userService.updateRole('user_owner', 'owner')).resolves.toMatchObject({
        role: 'owner',
      })
    })

    it('allows demoting an owner once a second active owner exists', async () => {
      seedSession('manager@horizonpartners.example.com')
      await userService.updateRole('user_administrator', 'owner')
      await expect(userService.updateRole('user_owner', 'manager')).resolves.toMatchObject({
        role: 'manager',
      })
    })

    // Restoring access grants rather than removes, so nothing guards it.
    it('allows restoring a disabled user', async () => {
      seedSession('owner@horizonpartners.example.com')
      await expect(userService.setStatus('user_disabled', 'active')).resolves.toMatchObject({
        status: 'active',
      })
    })

    it('skips self-protection when no session is stored but still guards the owner', async () => {
      await expect(userService.remove('user_agent')).resolves.toBeUndefined()
      await expect(userService.remove('user_owner')).rejects.toMatchObject({
        description: 'Your organization needs at least one Owner.',
      })
    })
  })
})
