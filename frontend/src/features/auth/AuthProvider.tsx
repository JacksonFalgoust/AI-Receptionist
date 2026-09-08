import { useCallback, useMemo, useState, type ReactNode } from 'react'

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

  const signIn = useCallback(async (email: string, password: string) => {
    const next = await authService.signIn({ email, password })
    setSession(next)
  }, [])

  const signOut = useCallback(async () => {
    await authService.signOut()
    setSession(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      signIn,
      signOut,
    }),
    [session, signIn, signOut],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
