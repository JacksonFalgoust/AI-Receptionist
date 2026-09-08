import { createContext } from 'react'

import type { Session, SessionUser } from '@/types'

export interface AuthContextValue {
  session: Session | null
  user: SessionUser | null
  signIn(email: string, password: string): Promise<void>
  signOut(): Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
