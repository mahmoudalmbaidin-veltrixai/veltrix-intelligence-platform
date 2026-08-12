/** Real cookie-session authentication adapter. */
import type { AuthService, LoginCredentials, Session } from './types'
import { apiClient } from '@/shared/lib/apiClient'
import { ApiError } from '@/shared/types/api'
import { authenticationResponseSchema, parseContract } from '@/shared/contracts/apiContracts'

export function parseSession(value: unknown): Session {
  const dto = parseContract(authenticationResponseSchema, value, 'authentication session')
  return {
    expiresAt: dto.session.expires_at,
    user: {
      id: dto.user.id,
      username: dto.user.username,
      email: dto.user.email,
      displayName: dto.user.display_name,
      status: dto.user.status,
      isPlatformAdmin: dto.user.is_platform_admin,
      mustChangePassword: dto.user.must_change_password,
      accountType: dto.user.account_type,
      jobTitle: dto.user.job_title ?? null,
      department: dto.user.department ?? null,
      phone: dto.user.phone ?? null,
      locale: dto.user.locale ?? null,
      timezone: dto.user.timezone ?? null,
      avatarUrl: dto.user.avatar_url ?? null,
      preferences: dto.user.preferences ?? {},
      createdAt: dto.user.created_at ?? null,
      lastLoginAt: dto.user.last_login_at ?? null,
      passwordChangedAt: dto.user.password_changed_at ?? null,
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
  async requestPasswordReset(identifier: string) {
    await apiClient.post<unknown>(
      '/auth/password-reset/request',
      { identifier },
      { skipAuthRefresh: true, notifyOnUnauthorized: false },
    )
  },
  async confirmPasswordReset(token: string, newPassword: string) {
    await apiClient.post<unknown>(
      '/auth/password-reset/confirm',
      { token, new_password: newPassword },
      { skipAuthRefresh: true, notifyOnUnauthorized: false },
    )
  },
  async changePassword(currentPassword: string, newPassword: string) {
    await apiClient.post<unknown>('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}
