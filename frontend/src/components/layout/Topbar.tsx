import { Bell, ChevronDown, Menu, Play } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/features/auth/useAuth'
import { paths } from '@/routes/paths'

function initials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

/**
 * Application header (PRD §6.2).
 *
 * Scaffold state: the organization selector, status badge, and notification
 * bell render but do not yet open their panels — those are separate TODO
 * items. Each is a real control with an accessible name so keyboard and
 * screen-reader behaviour is correct from the start.
 */
export function Topbar({ onOpenNav }: { onOpenNav: () => void }) {
  const { user } = useAuth()
  if (!user) return null

  return (
    <header className="sticky top-0 z-30 flex h-(--header-h) items-center justify-between gap-4 border-b border-border bg-surface/92 px-6 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          className="grid size-9 place-items-center rounded-sm border border-border text-ink-secondary hover:bg-canvas lg:hidden"
        >
          <Menu className="size-[18px]" aria-hidden="true" />
        </button>

        <button
          type="button"
          className="flex items-center gap-2 rounded-sm border border-border px-3 py-1.5 text-sm font-semibold hover:bg-canvas"
          aria-label={`Organization: ${user.organizationName}`}
        >
          <span className="size-2 rounded-full bg-brand" aria-hidden="true" />
          {user.organizationName}
          <ChevronDown className="size-3.5 text-ink-muted" aria-hidden="true" />
        </button>

        {/* PRD §31: status is conveyed by the text label, not the dot alone. */}
        <button
          type="button"
          className="hidden items-center gap-2 rounded-full bg-success-soft px-3 py-1.5 text-xs font-semibold text-success sm:flex"
          aria-label="Concierge status: Active"
        >
          <span className="size-2 rounded-full bg-success" aria-hidden="true" />
          Concierge Active
        </button>
      </div>

      <div className="flex items-center gap-2">
        <Link
          to={paths.test}
          className="flex items-center gap-2 rounded-sm bg-brand px-3.5 py-2 text-sm font-semibold text-ink-inverse hover:bg-brand-strong"
        >
          <Play className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline">Test Concierge</span>
        </Link>

        <button
          type="button"
          className="relative grid size-9 place-items-center rounded-sm border border-border text-ink-secondary hover:bg-canvas"
          aria-label="Notifications, 3 unread"
        >
          <Bell className="size-[18px]" strokeWidth={1.8} aria-hidden="true" />
          <span className="absolute -top-1 -right-1 grid size-4 place-items-center rounded-full bg-danger text-[0.6rem] font-bold text-ink-inverse">
            3
          </span>
        </button>

        <button
          type="button"
          className="grid size-9 place-items-center rounded-full bg-brand-soft text-xs font-bold text-brand-ink"
          aria-label={`Account for ${user.name}`}
        >
          {initials(user.name)}
        </button>
      </div>
    </header>
  )
}
