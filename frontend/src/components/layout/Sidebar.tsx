import { NavLink } from 'react-router-dom'

import { useAuth } from '@/features/auth/useAuth'
import { cn } from '@/lib/cn'
import { can } from '@/lib/permissions'
import { paths } from '@/routes/paths'

import { NAV_GROUPS, type NavItem } from './nav'

/**
 * Persistent navigation rail (PRD §6.1). On desktop it is a grid column; below
 * `lg` it slides in as a drawer, which `AppShell` opens and closes.
 */
export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth()
  if (!user) return null

  const visibleGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => can(user.role, item.permission)),
  })).filter((group) => group.items.length > 0)

  return (
    <aside
      className="flex h-full w-(--sidebar-w) flex-col bg-rail px-3 py-4 text-rail-text"
      aria-label="Primary"
    >
      <NavLink
        to={paths.overview}
        className="flex items-center gap-3 px-2.5 pt-1.5 pb-4 text-ink-inverse"
        onClick={onNavigate}
      >
        <img src="/logo.svg" alt="" width={34} height={34} className="shrink-0" />
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="text-[0.95rem] font-bold tracking-tight">
            GuideAnts <span className="text-brand">Concierge</span>
          </span>
          <span className="text-[0.7rem] font-medium text-rail-text-muted">
            AI customer operations
          </span>
        </span>
      </NavLink>

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-1" aria-label="Application">
        {visibleGroups.map((group, index) => (
          <div key={group.label ?? `group-${index}`} className={group.label ? 'mt-3.5' : undefined}>
            {group.label ? (
              <div className="px-3 pt-1.5 pb-2 text-[0.65rem] font-bold tracking-[0.08em] text-rail-text-muted uppercase">
                {group.label}
              </div>
            ) : null}
            {group.items.map((item) => (
              <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />
            ))}
          </div>
        ))}
      </nav>

      {/* PRD §24.1: setup progress stays visible until onboarding completes.
          Wired to real progress in Phase F; static until then. */}
      <div className="mt-3 border-t border-white/10 px-2.5 pt-3">
        <div className="flex flex-col gap-1.5 rounded-md bg-white/5 p-3" role="status">
          <span className="text-xs text-rail-text-muted">Concierge setup</span>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
            <span className="block h-full w-2/3 bg-brand" />
          </div>
          <span className="text-xs font-semibold text-[#e8eef3]">6 of 9 complete</span>
        </div>
      </div>
    </aside>
  )
}

function SidebarLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = item.icon

  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 rounded-sm px-3 py-2 text-sm font-medium transition-colors',
          'hover:bg-white/6 hover:text-white',
          isActive
            ? 'bg-brand/18 text-white shadow-[inset_3px_0_0_var(--color-brand)]'
            : 'text-rail-text',
        )
      }
    >
      <Icon className="size-[18px] shrink-0 opacity-90" strokeWidth={1.8} aria-hidden="true" />
      {item.label}
    </NavLink>
  )
}
