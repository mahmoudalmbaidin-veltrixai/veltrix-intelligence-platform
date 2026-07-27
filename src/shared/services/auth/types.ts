export interface LoginCredentials {
  /** Username (primary) or email — the backend accepts either. */
  username: string
  password: string
}

export type UserStatus = 'pending' | 'active' | 'locked' | 'disabled' | 'suspended' | 'deleted'

export interface AuthenticatedUser {
  id: string
  username?: string
  email?: string | null
  displayName: string
  status: UserStatus
  isPlatformAdmin: boolean
}

export interface Session {
  expiresAt: string
  user: AuthenticatedUser
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
  currentUser(): Promise<Session | null>
  /** Exchange a refresh token / re-validate the session. */
  refresh(): Promise<Session | null>
}
