/**
 * Authentication store: session bootstrap on app boot, login/logout, and the
 * post-login redirect target. The reactive UI context (role/org/workspace,
 * permissions, feature flags) is owned by the platform store; this store gates
 * access and manages the session lifecycle.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService, seedMockSession, type Session } from '@/shared/services/auth'
import { config } from '@/shared/config/env'
import { ApiError } from '@/shared/types/api'

export type AuthStatus = 'booting' | 'authenticated' | 'unauthenticated'

export const useAuthStore = defineStore('auth', () => {
  const status = ref<AuthStatus>('booting')
  const session = ref<Session | null>(null)
  const error = ref<ApiError | null>(null)
  const intendedRoute = ref<string | null>(null)

  const isAuthenticated = computed(() => status.value === 'authenticated')
  const isBooting = computed(() => status.value === 'booting')

  async function bootstrap(): Promise<void> {
    status.value = 'booting'
    // In mock mode the app boots "logged in" for reviewers.
    if (config.apiMode === 'mock') seedMockSession()
    try {
      const restored = await authService.bootstrap()
      session.value = restored
      status.value = restored ? 'authenticated' : 'unauthenticated'
    } catch {
      session.value = null
      status.value = 'unauthenticated'
    }
  }

  async function login(email: string, password: string): Promise<boolean> {
    error.value = null
    try {
      session.value = await authService.login({ email, password })
      status.value = 'authenticated'
      return true
    } catch (e) {
      error.value = ApiError.from(e)
      return false
    }
  }

  async function logout(): Promise<void> {
    await authService.logout()
    session.value = null
    status.value = 'unauthenticated'
  }

  /** Called by the API client on a 401 to force reauthentication. */
  function onUnauthorized(): void {
    session.value = null
    status.value = 'unauthenticated'
  }

  function setIntended(path: string): void {
    intendedRoute.value = path
  }
  function takeIntended(): string {
    const r = intendedRoute.value ?? '/home'
    intendedRoute.value = null
    return r
  }

  return {
    status, session, error, intendedRoute,
    isAuthenticated, isBooting,
    bootstrap, login, logout, onUnauthorized, setIntended, takeIntended,
  }
})
