import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const service = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  currentUser: vi.fn(),
  refresh: vi.fn(),
}))
vi.mock('@/shared/services/auth', () => ({ authService: service }))
vi.mock('@/shared/services/tenancy/apiTenancyService', () => ({
  tenancyService: { listOrganizations: vi.fn().mockResolvedValue([]), listWorkspaces: vi.fn().mockResolvedValue([]) },
}))

import { useAuthStore } from './auth'

const session = {
  expiresAt: '2026-07-21T12:00:00Z',
  user: { id: 'user-1', email: 'admin@veltrix.local', displayName: 'VIP Admin', status: 'active' as const },
}

describe('real authentication store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('bootstraps through the backend service', async () => {
    service.bootstrap.mockResolvedValue(session)
    const auth = useAuthStore()
    await auth.bootstrap()
    expect(service.bootstrap).toHaveBeenCalledOnce()
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.initialized).toBe(true)
  })

  it('has no fake-user fallback when bootstrap is unauthorized', async () => {
    service.bootstrap.mockResolvedValue(null)
    const auth = useAuthStore()
    await auth.bootstrap()
    expect(auth.status).toBe('unauthenticated')
    expect(auth.session).toBeNull()
  })

  it('logs in and out without retaining credentials or tokens', async () => {
    service.login.mockResolvedValue(session)
    service.logout.mockResolvedValue(undefined)
    const auth = useAuthStore()
    expect(await auth.login(session.user.email, 'not-retained')).toBe(true)
    expect(JSON.stringify(auth.$state)).not.toContain('not-retained')
    expect(JSON.stringify(auth.$state)).not.toContain('token')
    await auth.logout()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('records login failure and clears on unauthorized', async () => {
    service.login.mockRejectedValue(new Error('denied'))
    const auth = useAuthStore()
    expect(await auth.login('user@example.com', 'wrong')).toBe(false)
    expect(auth.error).not.toBeNull()
    auth.onUnauthorized()
    expect(auth.status).toBe('unauthenticated')
  })

  it('preserves and consumes the intended route', () => {
    const auth = useAuthStore()
    auth.setIntended('/dashboards')
    expect(auth.takeIntended()).toBe('/dashboards')
    expect(auth.takeIntended()).toBe('/home')
  })
})
