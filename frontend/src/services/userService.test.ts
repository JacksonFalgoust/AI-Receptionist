import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

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
})
