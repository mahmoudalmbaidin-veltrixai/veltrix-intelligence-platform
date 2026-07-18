import { describe, it, expect, beforeEach } from 'vitest'
import { mockAuthService } from './mockAuthService'
import { ApiError } from '@/shared/types/api'

describe('mockAuthService', () => {
  beforeEach(() => localStorage.clear())

  it('has no session before login', async () => {
    expect(await mockAuthService.bootstrap()).toBeNull()
    expect(await mockAuthService.currentUser()).toBeNull()
  })

  it('logs in and persists a session', async () => {
    const session = await mockAuthService.login({ email: 'a@b.com', password: 'pw' })
    expect(session.context.user.email).toBe('a@b.com')
    expect(await mockAuthService.bootstrap()).not.toBeNull()
    expect(await mockAuthService.currentUser()).not.toBeNull()
  })

  it('rejects empty credentials with field errors', async () => {
    await expect(mockAuthService.login({ email: '', password: '' })).rejects.toBeInstanceOf(ApiError)
    try {
      await mockAuthService.login({ email: '', password: 'x' })
    } catch (e) {
      expect((e as ApiError).kind).toBe('validation')
      expect((e as ApiError).fieldErrors?.some((f) => f.field === 'email')).toBe(true)
    }
  })

  it('clears the session on logout', async () => {
    await mockAuthService.login({ email: 'a@b.com', password: 'pw' })
    await mockAuthService.logout()
    expect(await mockAuthService.bootstrap()).toBeNull()
  })

  it('refreshes an active session', async () => {
    await mockAuthService.login({ email: 'a@b.com', password: 'pw' })
    expect(await mockAuthService.refresh()).not.toBeNull()
  })
})
