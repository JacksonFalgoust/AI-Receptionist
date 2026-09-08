import { buildMockSessionUser, MOCK_PASSWORD } from '@/mocks/session'
import type { Session } from '@/types'

import { delay, SESSION_STORAGE_KEY, USE_MOCKS } from './config'
import { AppError } from './errors'
import { http } from './http'

/**
 * Reference implementation of the service pattern every other service follows:
 * one interface, a mock implementation, an HTTP implementation, and a single
 * export chosen by `USE_MOCKS`. Components import only `authService` and never
 * learn which one they got.
 */

export interface SignInInput {
  email: string
  password: string
}

export interface AuthService {
  signIn(input: SignInInput): Promise<Session>
  signOut(): Promise<void>
  /** Reads the persisted session without a network round-trip. */
  getStoredSession(): Session | null
  requestPasswordReset(email: string): Promise<void>
}

const SESSION_TTL_MS = 1000 * 60 * 60 * 8

function persist(session: Session): void {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
}

function clear(): void {
  localStorage.removeItem(SESSION_STORAGE_KEY)
}

function readStoredSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null

    const session = JSON.parse(raw) as Session
    if (new Date(session.expiresAt).getTime() <= Date.now()) {
      clear()
      return null
    }
    return session
  } catch {
    clear()
    return null
  }
}

const invalidCredentials = new AppError({
  kind: 'validation',
  title: 'We could not sign you in',
  description: 'That email and password combination is not recognised.',
})

const mockAuthService: AuthService = {
  async signIn({ email, password }) {
    await delay()

    if (password !== MOCK_PASSWORD) {
      throw invalidCredentials
    }

    const session: Session = {
      token: `mock.${btoa(email)}.${Date.now()}`,
      user: buildMockSessionUser(email),
      expiresAt: new Date(Date.now() + SESSION_TTL_MS).toISOString(),
    }
    persist(session)
    return session
  },

  async signOut() {
    await delay(120)
    clear()
  },

  getStoredSession: readStoredSession,

  async requestPasswordReset() {
    await delay()
    // Intentionally always resolves. Revealing whether an account exists would
    // leak membership (USER_STORIES US-1.2: "If an account exists…").
  },
}

const httpAuthService: AuthService = {
  async signIn(input) {
    const session = await http.post<Session>('/auth/login', input)
    persist(session)
    return session
  },

  async signOut() {
    try {
      await http.post<void>('/auth/logout')
    } finally {
      // The local session must go even if the server call fails.
      clear()
    }
  },

  getStoredSession: readStoredSession,

  async requestPasswordReset(email) {
    await http.post<void>('/auth/password-reset', { email })
  },
}

export const authService: AuthService = USE_MOCKS
  ? mockAuthService
  : httpAuthService
