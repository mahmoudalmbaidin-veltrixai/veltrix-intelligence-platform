import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth'

describe('auth store (mock mode)', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('bootstraps to authenticated in mock mode (seeded session)', async () => {
    const auth = useAuthStore()
    expect(auth.isBooting).toBe(true)
    await auth.bootstrap()
    expect(auth.isAuthenticated).toBe(true)
  })

  it('logs out to unauthenticated', async () => {
    const auth = useAuthStore()
    await auth.bootstrap()
    await auth.logout()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.status).toBe('unauthenticated')
  })

  it('logs back in after logout', async () => {
    const auth = useAuthStore()
    await auth.bootstrap()
    await auth.logout()
    const ok = await auth.login('user@x.com', 'pw')
    expect(ok).toBe(true)
    expect(auth.isAuthenticated).toBe(true)
  })

  it('fails login on empty credentials and records the error', async () => {
    const auth = useAuthStore()
    await auth.bootstrap()
    await auth.logout()
    const ok = await auth.login('', '')
    expect(ok).toBe(false)
    expect(auth.error?.kind).toBe('validation')
  })

  it('preserves and returns the intended route', () => {
    const auth = useAuthStore()
    auth.setIntended('/dashboards/db_exec/edit')
    expect(auth.takeIntended()).toBe('/dashboards/db_exec/edit')
    // consumed after taking
    expect(auth.takeIntended()).toBe('/home')
  })

  it('drops to unauthenticated on a 401 signal', async () => {
    const auth = useAuthStore()
    await auth.bootstrap()
    auth.onUnauthorized()
    expect(auth.isAuthenticated).toBe(false)
  })
})
