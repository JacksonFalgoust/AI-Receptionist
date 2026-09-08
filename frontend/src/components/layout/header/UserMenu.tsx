import { useNavigate } from 'react-router-dom'

import { Dropdown } from '@/components/ui/Dropdown'
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

const MENU_ITEM_CLASSES =
  'block w-full rounded-sm px-3 py-2 text-left text-sm text-ink hover:bg-canvas disabled:cursor-not-allowed disabled:text-ink-muted disabled:hover:bg-transparent'

/**
 * PRD §6.2 user menu. Profile, Organization settings, and Account settings have
 * no routes yet, so they ship visibly present but disabled — the same treatment
 * `LoginPage` gives the SSO buttons. Logout is live.
 */
export function UserMenu() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  async function handleSignOut() {
    await signOut()
    navigate(paths.login, { replace: true })
  }

  return (
    <Dropdown
      align="end"
      trigger={
        <button
          type="button"
          aria-label={`Account for ${user.name}`}
          className="grid size-9 place-items-center rounded-full bg-brand-soft text-xs font-bold text-brand-ink"
        >
          {initials(user.name)}
        </button>
      }
    >
      <div className="w-56">
        <div className="border-b border-border px-3 py-2">
          <p className="truncate text-sm font-semibold text-ink">{user.name}</p>
          <p className="truncate text-xs text-ink-muted">{user.email}</p>
        </div>

        <div className="p-1">
          {['Profile', 'Organization settings', 'Account settings'].map((label) => (
            <button
              key={label}
              type="button"
              role="menuitem"
              disabled
              title="This is not available yet"
              className={MENU_ITEM_CLASSES}
            >
              {label}
            </button>
          ))}

          <button
            type="button"
            role="menuitem"
            onClick={() => void handleSignOut()}
            className={MENU_ITEM_CLASSES}
          >
            Log out
          </button>
        </div>
      </div>
    </Dropdown>
  )
}
