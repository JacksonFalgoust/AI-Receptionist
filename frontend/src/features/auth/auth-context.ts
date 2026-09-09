import { createContext } from 'react'

import type { Session, SessionUser } from '@/types'

export interface AuthContextValue {
  session: Session | null
  user: SessionUser | null
  /** True when the session was dropped by a 401 rather than a deliberate sign-out. */
  sessionExpired: boolean
  signIn(email: string, password: string): Promise<void>
  signOut(): Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
