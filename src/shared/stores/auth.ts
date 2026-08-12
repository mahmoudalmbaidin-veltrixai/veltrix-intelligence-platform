/** Authoritative in-memory authentication state backed by HTTP-only cookies. */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authService, type Session } from '@/shared/services/auth'
import { usePlatformStore } from '@/shared/stores/platform'
import { useThemeStore } from '@/shared/stores/theme'
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
  let loginPromise: Promise<boolean> | null = null
  let sessionGeneration = 0

  const isAuthenticated = computed(() => status.value === 'authenticated')
  const isBooting = computed(() => !initialized.value || status.value === 'loading')
  // Drives the forced password-change flow; the backend independently blocks all
  // business routes for a flagged user, so this only governs client routing.
  const mustChangePassword = computed(() => session.value?.user.mustChangePassword === true)

  async function clearSession(): Promise<void> {
    session.value = null
    status.value = 'unauthenticated'
    usePlatformStore().clearContext()
  }

  async function establishSession(value: Session, generation: number): Promise<boolean> {
    const platform = usePlatformStore()
    platform.hydrateAuthenticatedUser(value.user)
    // Apply the user's server-stored appearance preferences on sign-in so theme,
    // density and reduced-motion follow them across devices.
    useThemeStore().hydrate(value.user.preferences)
    await platform.bootstrapTenancy(true)
    if (generation !== sessionGeneration) return false
    if (platform.status === 'error') {
      throw platform.error ?? new Error('Authenticated tenant bootstrap failed.')
    }
    session.value = value
    status.value = 'authenticated'
    return true
  }

  async function bootstrap(): Promise<void> {
    if (bootstrapPromise) return bootstrapPromise
    const generation = ++sessionGeneration
    status.value = 'loading'
    bootstrapPromise = (async () => {
      try {
        const restored = await authService.bootstrap()
        if (restored) await establishSession(restored, generation)
        else if (generation === sessionGeneration) await clearSession()
      } catch (cause) {
        if (generation === sessionGeneration) {
          error.value = ApiError.from(cause)
          await clearSession()
        }
      } finally {
        if (generation === sessionGeneration) initialized.value = true
        bootstrapPromise = null
      }
    })()
    return bootstrapPromise
  }

  async function login(identifier: string, password: string): Promise<boolean> {
    if (loginPromise) return loginPromise
    const generation = ++sessionGeneration
    error.value = null
    status.value = 'loading'
    loginPromise = (async () => {
      try {
        await authService.login({ username: identifier, password })
        // The login response alone does not prove that Firefox adopted the
        // HTTP-only cookie. Confirm through the same endpoint used on refresh,
        // then finish tenant/authorization bootstrap before reporting success.
        const confirmed = await authService.bootstrap()
        if (!confirmed) throw new Error('The authenticated session could not be confirmed.')
        const established = await establishSession(confirmed, generation)
        if (!established) return false
        initialized.value = true
        return true
      } catch (cause) {
        if (generation === sessionGeneration) {
          error.value = ApiError.from(cause)
          await clearSession()
          initialized.value = true
        }
        return false
      } finally {
        loginPromise = null
      }
    })()
    return loginPromise
  }

  async function logout(): Promise<void> {
    ++sessionGeneration
    try {
      await authService.logout()
    } finally {
      await clearSession()
      initialized.value = true
    }
  }

  async function refreshSession(): Promise<boolean> {
    const generation = ++sessionGeneration
    const refreshed = await authService.refresh()
    if (!refreshed) {
      await clearSession()
      return false
    }
    return establishSession(refreshed, generation)
  }

  function onUnauthorized(): void {
    ++sessionGeneration
    if (status.value === 'authenticated') expiredTick.value++
    void clearSession()
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
