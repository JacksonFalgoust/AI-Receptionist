import { Menu, Play } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { useAuth } from '@/features/auth/useAuth'
import { useTestConciergeDrawer } from '@/features/testConcierge/useTestConciergeDrawer'
import { can } from '@/lib/permissions'

import { ConciergeStatusPanel } from './header/ConciergeStatusPanel'
import { NotificationCenter } from './header/NotificationCenter'
import { OrganizationMenu } from './header/OrganizationMenu'
import { UserMenu } from './header/UserMenu'

/**
 * Application header (PRD §6.2). Composition only — each of the four controls
 * owns its own data and open/close behaviour, so this file stays layout.
 */
export function Topbar({ onOpenNav }: { onOpenNav: () => void }) {
  const { user } = useAuth()
  const { open } = useTestConciergeDrawer()
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

        <OrganizationMenu />
        <ConciergeStatusPanel />
      </div>

      <div className="flex items-center gap-2">
        {can(user.role, 'use:test') ? (
          <Button variant="primary" size="sm" onClick={open}>
            <Play className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Test Concierge</span>
          </Button>
        ) : null}

        <NotificationCenter />
        <UserMenu />
      </div>
    </header>
  )
}
