/** Authoritative in-memory authentication state backed by HTTP-only cookies. */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authService, type Session } from '@/shared/services/auth'
import { usePlatformStore } from '@/shared/stores/platform'
import { ApiError } from '@/shared/types/api'

export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'unauthenticated' | 'error'

export const useAuthStore = defineStore('auth', () => {
  const status = ref<AuthStatus>('idle')
  const initialized = ref(false)
  const session = ref<Session | null>(null)
  const error = ref<ApiError | null>(null)
  const intendedRoute = ref<string | null>(null)
  const expiredTick = ref(0)
  let bootstrapPromise: Promise<void> | null = null

  const isAuthenticated = computed(() => status.value === 'authenticated')
  const isBooting = computed(() => !initialized.value || status.value === 'loading')
  // Drives the forced password-change flow; the backend independently blocks all
  // business routes for a flagged user, so this only governs client routing.
  const mustChangePassword = computed(() => session.value?.user.mustChangePassword === true)

  async function applySession(value: Session | null): Promise<void> {
    session.value = value
    status.value = value ? 'authenticated' : 'unauthenticated'
    const platform = usePlatformStore()
    if (value) {
      platform.hydrateAuthenticatedUser(value.user)
      await platform.bootstrapTenancy()
    } else platform.clearContext()
  }

  async function bootstrap(): Promise<void> {
    if (bootstrapPromise) return bootstrapPromise
    status.value = 'loading'
    bootstrapPromise = (async () => {
      try {
        await applySession(await authService.bootstrap())
      } catch (cause) {
        error.value = ApiError.from(cause)
        await applySession(null)
      } finally {
        initialized.value = true
        bootstrapPromise = null
      }
    })()
    return bootstrapPromise
  }

  async function login(identifier: string, password: string): Promise<boolean> {
    error.value = null
    status.value = 'loading'
    try {
      await applySession(await authService.login({ username: identifier, password }))
      initialized.value = true
      return true
    } catch (cause) {
      error.value = ApiError.from(cause)
      await applySession(null)
      initialized.value = true
      return false
    }
  }

  async function logout(): Promise<void> {
    try {
      await authService.logout()
    } finally {
      await applySession(null)
      initialized.value = true
    }
  }

  async function refreshSession(): Promise<boolean> {
    const refreshed = await authService.refresh()
    await applySession(refreshed)
    return refreshed != null
  }

  function onUnauthorized(): void {
    if (status.value === 'authenticated') expiredTick.value++
    void applySession(null)
    initialized.value = true
  }

  function setIntended(path: string): void {
    intendedRoute.value = path
  }
  function takeIntended(): string {
    const path = intendedRoute.value ?? '/home'
    intendedRoute.value = null
    return path
  }

  return {
    status,
    initialized,
    session,
    error,
    intendedRoute,
    expiredTick,
    isAuthenticated,
    isBooting,
    mustChangePassword,
    bootstrap,
    login,
    logout,
    refreshSession,
    onUnauthorized,
    setIntended,
    takeIntended,
  }
})
