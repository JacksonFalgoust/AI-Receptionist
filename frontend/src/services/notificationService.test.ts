import { beforeEach, describe, expect, it } from 'vitest'

import { resetStore } from '@/mocks/store'

import { notificationService } from './notificationService'

describe('notificationService', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns notifications newest first', async () => {
    const notifications = await notificationService.list()
    const timestamps = notifications.map((item) => new Date(item.at).getTime())
    expect([...timestamps].sort((a, b) => b - a)).toEqual(timestamps)
  })

  it('marks one notification as read', async () => {
    const before = await notificationService.list()
    const unread = before.find((item) => !item.read)
    expect(unread).toBeDefined()

    await notificationService.markRead(unread!.id)

    const after = await notificationService.list()
    expect(after.find((item) => item.id === unread!.id)?.read).toBe(true)
  })

  it('marks every notification as read', async () => {
    await notificationService.markAllRead()
    const after = await notificationService.list()
    expect(after.every((item) => item.read)).toBe(true)
  })

  it('raises a not_found AppError for an unknown id', async () => {
    await expect(notificationService.markRead('ntf_missing')).rejects.toMatchObject({
      kind: 'not_found',
    })
  })
})
