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
})
