/**
 * Live authentication adapter (placeholder wiring). Uses the centralized API
 * client and prefers secure http-only cookie sessions (credentials: 'include').
 * Endpoint paths reflect the expected backend contract; see BACKEND_INTEGRATION.
 *
 *   POST /auth/login        -> Session
 *   POST /auth/logout       -> 204
 *   GET  /auth/me           -> AuthContext
 *   POST /auth/refresh      -> Session
 */
import type { AuthService, LoginCredentials, Session } from './types'
import type { AuthContext } from '@/shared/types/identity'
import { apiClient } from '@/shared/lib/apiClient'
import { ApiError } from '@/shared/types/api'

export const apiAuthService: AuthService = {
  async bootstrap() {
    try {
      const context = await apiClient.get<AuthContext>('/auth/me')
      return { expiresAt: '', context }
    } catch (e) {
      if (e instanceof ApiError && e.kind === 'unauthorized') return null
      throw e
    }
  },
  async login(credentials: LoginCredentials) {
    return apiClient.post<Session>('/auth/login', credentials)
  },
  async logout() {
    await apiClient.post<void>('/auth/logout')
  },
  async currentUser() {
    try {
      return await apiClient.get<AuthContext>('/auth/me')
    } catch (e) {
      if (e instanceof ApiError && e.kind === 'unauthorized') return null
      throw e
    }
  },
  async refresh() {
    try {
      return await apiClient.post<Session>('/auth/refresh')
    } catch (e) {
      if (e instanceof ApiError && e.kind === 'unauthorized') return null
      throw e
    }
  },
}
