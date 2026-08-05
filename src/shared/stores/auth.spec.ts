import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const service = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  currentUser: vi.fn(),
  refresh: vi.fn(),
}))
const tenancy = vi.hoisted(() => ({
  listOrganizations: vi.fn(),
  listWorkspaces: vi.fn(),
}))
const governance = vi.hoisted(() => ({ authorizationContext: vi.fn() }))
vi.mock('@/shared/services/auth', () => ({ authService: service }))
vi.mock('@/shared/services/tenancy/apiTenancyService', () => ({
  tenancyService: tenancy,
}))
vi.mock('@/shared/services/governance/apiGovernanceService', () => ({ governanceService: governance }))

import { useAuthStore } from './auth'

const session = {
  expiresAt: '2026-07-21T12:00:00Z',
  user: { id: 'user-1', email: 'admin@veltrix.local', displayName: 'VIP Admin', status: 'active' as const },
}

describe('real authentication store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    tenancy.listOrganizations.mockResolvedValue([])
    tenancy.listWorkspaces.mockResolvedValue([])
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
    service.bootstrap.mockResolvedValue(session)
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

  it('does not report login success until the cookie-backed current user is confirmed', async () => {
    let confirm!: (value: typeof session) => void
    service.login.mockResolvedValue(session)
    service.bootstrap.mockReturnValue(new Promise((resolve) => (confirm = resolve)))
    const auth = useAuthStore()
    const pending = auth.login('user@example.com', 'not-retained')
    await Promise.resolve()
    expect(auth.status).toBe('loading')
    confirm(session)
    await expect(pending).resolves.toBe(true)
    expect(auth.status).toBe('authenticated')
  })

  it('does not report login success until delayed organization bootstrap settles', async () => {
    let organizations!: (value: never[]) => void
    service.login.mockResolvedValue(session)
    service.bootstrap.mockResolvedValue(session)
    tenancy.listOrganizations.mockReturnValue(new Promise((resolve) => (organizations = resolve)))
    const auth = useAuthStore()
    const pending = auth.login('user@example.com', 'not-retained')
    await Promise.resolve()
    expect(auth.status).toBe('loading')
    organizations([])
    await expect(pending).resolves.toBe(true)
  })

  it('fails closed when current-user confirmation fails after login returned success', async () => {
    service.login.mockResolvedValue(session)
    service.bootstrap.mockResolvedValue(null)
    const auth = useAuthStore()
    await expect(auth.login('user@example.com', 'not-retained')).resolves.toBe(false)
    expect(auth.status).toBe('unauthenticated')
    expect(auth.error).not.toBeNull()
  })

  it('joins duplicate login submissions into one backend lifecycle', async () => {
    service.login.mockResolvedValue(session)
    service.bootstrap.mockResolvedValue(session)
    const auth = useAuthStore()
    const first = auth.login('user@example.com', 'not-retained')
    const second = auth.login('user@example.com', 'not-retained')
    await expect(Promise.all([first, second])).resolves.toEqual([true, true])
    expect(service.login).toHaveBeenCalledOnce()
    expect(service.bootstrap).toHaveBeenCalledOnce()
  })

  it('ignores a stale login response after unauthorized invalidates the attempt', async () => {
    let completeLogin!: (value: typeof session) => void
    service.login.mockReturnValue(new Promise((resolve) => (completeLogin = resolve)))
    service.bootstrap.mockResolvedValue(session)
    const auth = useAuthStore()
    const pending = auth.login('user@example.com', 'not-retained')
    auth.onUnauthorized()
    completeLogin(session)
    await expect(pending).resolves.toBe(false)
    expect(auth.status).toBe('unauthenticated')
  })

  it('preserves and consumes the intended route', () => {
    const auth = useAuthStore()
    auth.setIntended('/dashboards')
    expect(auth.takeIntended()).toBe('/dashboards')
    expect(auth.takeIntended()).toBe('/home')
  })
})
