import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { onSessionExpired } from '@/lib/sessionExpiry'
import { authService } from '@/services/authService'
import type { Session } from '@/types'

import { AuthContext, type AuthContextValue } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  // Reading the stored session is synchronous, so it belongs in the state
  // initialiser rather than an effect — this way the first render already knows
  // whether the user is signed in and a refresh never flashes the login screen.
  const [session, setSession] = useState<Session | null>(() =>
    authService.getStoredSession(),
  )
  const [sessionExpired, setSessionExpired] = useState(false)

  // US-0.4: a 401 from any query or mutation lands here. Dropping the session
  // is enough — ProtectedRoute already redirects whenever there is no user.
  useEffect(
    () =>
      onSessionExpired(() => {
        // The token is already rejected, so a failed logout call changes nothing.
        void authService.signOut().catch(() => {})
        setSession(null)
        setSessionExpired(true)
      }),
    [],
  )

  const signIn = useCallback(async (email: string, password: string) => {
    const next = await authService.signIn({ email, password })
    setSession(next)
    setSessionExpired(false)
  }, [])

  const signOut = useCallback(async () => {
    await authService.signOut()
    setSession(null)
    setSessionExpired(false)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      sessionExpired,
      signIn,
      signOut,
    }),
    [session, sessionExpired, signIn, signOut],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
