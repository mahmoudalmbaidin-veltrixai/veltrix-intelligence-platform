import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: client }))

import { apiAuthService } from './apiAuthService'

const response = {
  user: { id: 'user-1', email: 'admin@veltrix.local', display_name: 'VIP Admin', status: 'active' },
  session: { expires_at: '2026-07-21T12:00:00Z' },
}

describe('API authentication adapter', () => {
  beforeEach(() => vi.clearAllMocks())
  it('maps backend login without exposing tokens', async () => {
    client.post.mockResolvedValue(response)
    const session = await apiAuthService.login({ email: 'admin@veltrix.local', password: 'secret' })
    expect(session.user.displayName).toBe('VIP Admin')
    expect(JSON.stringify(session)).not.toContain('token')
  })
  it('bootstraps from /auth/me', async () => {
    client.get.mockResolvedValue(response)
    expect((await apiAuthService.bootstrap())?.user.email).toBe('admin@veltrix.local')
    expect(client.get).toHaveBeenCalledWith('/auth/me')
  })
  it('calls logout and refresh endpoints', async () => {
    client.post.mockResolvedValueOnce(undefined).mockResolvedValueOnce(response)
    await apiAuthService.logout()
    expect(await apiAuthService.refresh()).not.toBeNull()
    expect(client.post.mock.calls.map((call) => call[0])).toEqual(['/auth/logout', '/auth/refresh'])
  })
  it('surfaces the forced-change flag from the session', async () => {
    client.get.mockResolvedValue({
      ...response,
      user: { ...response.user, must_change_password: true },
    })
    expect((await apiAuthService.bootstrap())?.user.mustChangePassword).toBe(true)
  })
  it('requests a password reset via the non-disclosing endpoint', async () => {
    client.post.mockResolvedValue(undefined)
    await apiAuthService.requestPasswordReset('someone@vip.test')
    expect(client.post).toHaveBeenCalledWith(
      '/auth/password-reset/request',
      { identifier: 'someone@vip.test' },
      expect.objectContaining({ skipAuthRefresh: true }),
    )
  })
  it('confirms a password reset with token + new password (snake_case body)', async () => {
    client.post.mockResolvedValue(undefined)
    await apiAuthService.confirmPasswordReset('tok-123', 'Rotated passphrase 2026!')
    expect(client.post).toHaveBeenCalledWith(
      '/auth/password-reset/confirm',
      { token: 'tok-123', new_password: 'Rotated passphrase 2026!' },
      expect.objectContaining({ skipAuthRefresh: true }),
    )
  })
  it('changes the current password (snake_case body)', async () => {
    client.post.mockResolvedValue(undefined)
    await apiAuthService.changePassword('Old passphrase 2026', 'Rotated passphrase 2026!')
    expect(client.post).toHaveBeenCalledWith('/auth/change-password', {
      current_password: 'Old passphrase 2026',
      new_password: 'Rotated passphrase 2026!',
    })
  })
})
