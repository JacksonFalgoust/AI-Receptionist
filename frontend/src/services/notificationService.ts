import { sortByDesc } from '@/mocks/query'
import { store } from '@/mocks/store'
import type { Id, Notification } from '@/types'

import { delay, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

/** PRD §6.2: the notification centre's data source (A7 must not hard-code it). */
export interface NotificationService {
  list(): Promise<Notification[]>
  markRead(id: Id): Promise<void>
  markAllRead(): Promise<void>
}

function notFound(id: Id): AppError {
  return new AppError({
    kind: 'not_found',
    title: 'Notification not found',
    description: `That notification no longer exists (${id}).`,
  })
}

const mockNotificationService: NotificationService = {
  async list() {
    await delay()
    return sortByDesc(store.notifications, (item) => item.at)
  },

  async markRead(id) {
    await delay(80)
    const notification = store.notifications.find((item) => item.id === id)
    if (!notification) throw notFound(id)
    notification.read = true
  },

  async markAllRead() {
    await delay(80)
    for (const notification of store.notifications) {
      notification.read = true
    }
  },
}

const httpNotificationService: NotificationService = {
  list: () => http.get<Notification[]>('/notifications'),
  markRead: (id) => http.post<void>(`/notifications/${id}/read`),
  markAllRead: () => http.post<void>('/notifications/read-all'),
}

export const notificationService: NotificationService = USE_MOCKS
  ? mockNotificationService
  : httpNotificationService
