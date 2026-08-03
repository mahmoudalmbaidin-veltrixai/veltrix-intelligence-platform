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
  /** When true the user must complete a forced password change before continuing. */
  mustChangePassword: boolean
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
  /** Request a password-reset link (non-disclosing; resolves regardless of match). */
  requestPasswordReset(identifier: string): Promise<void>
  /** Complete a password reset with a single-use token. */
  confirmPasswordReset(token: string, newPassword: string): Promise<void>
  /** Change the signed-in user's password (revokes all sessions server-side). */
  changePassword(currentPassword: string, newPassword: string): Promise<void>
}
