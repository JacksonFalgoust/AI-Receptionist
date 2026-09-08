import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

/**
 * Authenticated layout: persistent rail on desktop, drawer below `lg`
 * (PRD §6.1, USER_STORIES US-0.1).
 *
 * The drawer closes on navigation via each link's `onNavigate`, so no effect
 * needs to watch the location.
 */
export function AppShell() {
  const [navOpen, setNavOpen] = useState(false)

  useEffect(() => {
    if (!navOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNavOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [navOpen])

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[var(--sidebar-w)_1fr]">
      {/* Desktop rail */}
      <div className="sticky top-0 hidden h-screen lg:block">
        <Sidebar />
      </div>

      {/* Mobile drawer. Unmounted when closed so its links are not duplicated
          in the accessibility tree or reachable by tab from behind the page —
          the desktop rail above is only display:none, which browsers hide but
          which would otherwise leave two copies of every nav link in the DOM. */}
      {navOpen ? (
        <div className="lg:hidden">
          <div
            className="fixed inset-0 z-50 bg-ink/50"
            onClick={() => setNavOpen(false)}
            aria-hidden="true"
          />
          <div className="fixed inset-y-0 left-0 z-50">
            <Sidebar onNavigate={() => setNavOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-col">
        <Topbar onOpenNav={() => setNavOpen(true)} />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
