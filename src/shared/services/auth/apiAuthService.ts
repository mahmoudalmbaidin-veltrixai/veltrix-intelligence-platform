/** Real cookie-session authentication adapter. */
import type { AuthService, LoginCredentials, Session } from './types'
import { apiClient } from '@/shared/lib/apiClient'
import { ApiError } from '@/shared/types/api'
import { authenticationResponseSchema, parseContract } from '@/shared/contracts/apiContracts'

function parseSession(value: unknown): Session {
  const dto = parseContract(authenticationResponseSchema, value, 'authentication session')
  return {
    expiresAt: dto.session.expires_at,
    user: {
      id: dto.user.id,
      email: dto.user.email,
      displayName: dto.user.display_name,
      status: dto.user.status,
      isPlatformAdmin: dto.user.is_platform_admin,
    },
  }
}

export const apiAuthService: AuthService = {
  async bootstrap() {
    try {
      return parseSession(await apiClient.get<unknown>('/auth/me'))
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthorized') return null
      throw error
    }
  },
  async login(credentials: LoginCredentials) {
    return parseSession(
      await apiClient.post<unknown>('/auth/login', credentials, {
        skipAuthRefresh: true,
        notifyOnUnauthorized: false,
      }),
    )
  },
  async logout() {
    await apiClient.post<void>('/auth/logout', undefined, { skipAuthRefresh: true })
  },
  async currentUser() {
    try {
      return parseSession(await apiClient.get<unknown>('/auth/me'))
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthorized') return null
      throw error
    }
  },
  async refresh() {
    try {
      return parseSession(await apiClient.post<unknown>('/auth/refresh', undefined, { skipAuthRefresh: true }))
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthorized') return null
      throw error
    }
  },
}
