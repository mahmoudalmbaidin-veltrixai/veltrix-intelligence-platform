import type { AuthContext } from '@/shared/types/identity'

export interface LoginCredentials {
  email: string
  password: string
}

export interface Session {
  /** Short-lived access token abstraction. In cookie-session mode this may be empty. */
  token?: string
  expiresAt: string
  context: AuthContext
}

/**
 * Authentication service contract. Both the mock and live adapters implement it.
 * Token storage is intentionally abstracted — the live adapter prefers secure
 * http-only cookies (credentials: 'include') and only exposes a token when the
 * backend requires bearer auth.
 */
export interface AuthService {
  /** Restore an existing session on app boot (cookie/refresh). Returns null if none. */
  bootstrap(): Promise<Session | null>
  login(credentials: LoginCredentials): Promise<Session>
  logout(): Promise<void>
  currentUser(): Promise<AuthContext | null>
  /** Exchange a refresh token / re-validate the session. */
  refresh(): Promise<Session | null>
}
