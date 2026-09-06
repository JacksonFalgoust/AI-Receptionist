import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '@/features/auth/useAuth'
import { can, type Permission } from '@/lib/permissions'

import { paths } from './paths'

/**
 * Gate for every authenticated route (PRD §40).
 *
 * `permission` additionally restricts a route to roles that hold it. This is a
 * navigation guard, not a security boundary — the backend must enforce the
 * same rules.
 */
export function ProtectedRoute({ permission }: { permission?: Permission }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) {
    return <Navigate to={paths.login} state={{ from: location }} replace />
  }

  if (permission && !can(user.role, permission)) {
    return <Navigate to={paths.overview} replace />
  }

  return <Outlet />
}
