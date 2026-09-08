import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  Bell,
  CreditCard,
  PlugZap,
  Settings,
  ShieldAlert,
  UserRoundCheck,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'

import { Dropdown } from '@/components/ui/Dropdown'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { relativeTime } from '@/lib/formatDate'
import { notificationService } from '@/services/notificationService'
import type { NotificationKind } from '@/types'

const NOTIFICATIONS_KEY = ['notifications']

/** PRD §6.2 lists these six sources; each gets its own icon. */
const KIND_ICONS: Record<NotificationKind, ComponentType<{ className?: string }>> = {
  integration_failure: PlugZap,
  escalation: UserRoundCheck,
  workflow_error: AlertTriangle,
  configuration_issue: Settings,
  usage_limit: CreditCard,
  security_event: ShieldAlert,
}

export function NotificationCenter() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => notificationService.list(),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY })

  const markRead = useMutation({
    mutationFn: (id: string) => notificationService.markRead(id),
    onSuccess: invalidate,
  })
  const markAllRead = useMutation({
    mutationFn: () => notificationService.markAllRead(),
    onSuccess: invalidate,
  })

  const unreadCount = query.data?.filter((notification) => !notification.read).length ?? 0

  return (
    <Dropdown
      align="end"
      role="dialog"
      label="Notifications"
      trigger={
        <button
          type="button"
          aria-label={
            unreadCount ? `Notifications, ${unreadCount} unread` : 'Notifications, no unread'
          }
          className="relative grid size-9 place-items-center rounded-sm border border-border text-ink-secondary hover:bg-canvas"
        >
          <Bell className="size-[18px]" strokeWidth={1.8} aria-hidden="true" />
          {unreadCount ? (
            <span
              aria-hidden="true"
              className="absolute -top-1 -right-1 grid size-4 place-items-center rounded-full bg-danger text-[0.6rem] font-bold text-ink-inverse"
            >
              {unreadCount}
            </span>
          ) : null}
        </button>
      }
    >
      <div className="w-80">
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <span className="text-sm font-semibold text-ink">Notifications</span>
          <button
            type="button"
            onClick={() => markAllRead.mutate()}
            disabled={unreadCount === 0 || markAllRead.isPending}
            className="text-xs font-semibold text-brand-ink hover:underline disabled:cursor-not-allowed disabled:text-ink-muted disabled:no-underline"
          >
            Mark all as read
          </button>
        </div>

        <QueryBoundary
          query={query}
          skeletonRows={4}
          isEmpty={(notifications) => notifications.length === 0}
          empty={{
            title: 'You are all caught up',
            description: 'Integration, escalation, and usage alerts will appear here.',
          }}
        >
          {(notifications) => (
            <ul className="max-h-96 overflow-y-auto">
              {notifications.map((notification) => {
                const Icon = KIND_ICONS[notification.kind]
                return (
                  <li key={notification.id}>
                    <Link
                      to={notification.href ?? '#'}
                      onClick={() => {
                        if (!notification.read) markRead.mutate(notification.id)
                      }}
                      className="flex gap-3 border-b border-border px-3 py-2.5 last:border-b-0 hover:bg-canvas"
                    >
                      <Icon className="mt-0.5 size-4 shrink-0 text-ink-muted" />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-ink">{notification.title}</p>
                        <p className="text-xs text-ink-secondary">{notification.body}</p>
                        <p className="mt-0.5 text-xs text-ink-muted">
                          {/* Separate elements: a combined text node would read
                              "12 minutes ago · Unread" as one string. */}
                          <span>{relativeTime(notification.at)}</span>
                          {notification.read ? null : (
                            <span className="ml-1 font-semibold text-brand-ink">· Unread</span>
                          )}
                        </p>
                      </div>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </QueryBoundary>
      </div>
    </Dropdown>
  )
}
