import { apiAuthService } from './apiAuthService'

export type { AuthenticatedUser, AuthService, Session, LoginCredentials, UserStatus } from './types'

/** Authentication is always backend-backed; domain modules may remain mock-selected independently. */
export const authService = apiAuthService
