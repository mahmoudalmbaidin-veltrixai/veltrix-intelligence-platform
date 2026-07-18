/**
 * Authentication store: authoritative session lifecycle. On bootstrap/login it
 * hydrates the platform context from the session (QA VIP-FE-H001); on
 * logout/expiry it clears context (VIP-FE-H002). Mock logout is durable — a
 * deliberate sign-out is remembered so a refresh does not re-seed a session
 * (VIP-FE-H013).
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService, seedMockSession, type Session } from '@/shared/services/auth'
import { usePlatformStore } from '@/shared/stores/platform'
import { config } from '@/shared/config/env'
import { ApiError } from '@/shared/types/api'
import { LocalStore } from '@/shared/lib/mock'

export type AuthStatus = 'booting' | 'authenticated' | 'unauthenticated'

const logoutFlag = new LocalStore<{ signedOut: boolean }>('vip.auth.signedout')

export const useAuthStore = defineStore('auth', () => {
  const status = ref<AuthStatus>('booting')
  const session = ref<Session | null>(null)
  const error = ref<ApiError | null>(null)
  const intendedRoute = ref<string | null>(null)
  /** Bumped whenever a session expires (401) so the router can react. */
  const expiredTick = ref(0)

  const isAuthenticated = computed(() => status.value === 'authenticated')
  const isBooting = computed(() => status.value === 'booting')

  function applySession(s: Session | null) {
    session.value = s
    status.value = s ? 'authenticated' : 'unauthenticated'
    const platform = usePlatformStore()
    if (s) platform.hydrate(s.context)
    else platform.clearContext()
  }

  async function bootstrap(): Promise<void> {
    status.value = 'booting'
    const deliberatelyOut = logoutFlag.read({ signedOut: false }).signedOut
    // Mock mode boots "logged in" for reviewers — unless the user deliberately
    // signed out (durable logout).
    if (config.apiMode === 'mock' && !deliberatelyOut) seedMockSession()
    try {
      applySession(await authService.bootstrap())
    } catch {
      applySession(null)
    }
  }

  async function login(email: string, password: string): Promise<boolean> {
    error.value = null
    try {
      const s = await authService.login({ email, password })
      logoutFlag.write({ signedOut: false })
      applySession(s)
      return true
    } catch (e) {
      error.value = ApiError.from(e)
      return false
    }
  }

  async function logout(): Promise<void> {
    await authService.logout()
    logoutFlag.write({ signedOut: true })
    applySession(null)
  }

  /** Called by the API client on a 401 to force reauthentication. */
  function onUnauthorized(): void {
    if (status.value !== 'authenticated') return
    applySession(null)
    expiredTick.value++
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
    status,
    session,
    error,
    intendedRoute,
    expiredTick,
    isAuthenticated,
    isBooting,
    bootstrap,
    login,
    logout,
    onUnauthorized,
    setIntended,
    takeIntended,
  }
})
