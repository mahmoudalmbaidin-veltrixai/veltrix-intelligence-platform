import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  patch: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
  uploadRaw: vi.fn(),
  download: vi.fn(),
}))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: client }))

import { settingsService } from './settings.service'

const AUTH_RESPONSE = {
  user: {
    id: '11111111-1111-1111-1111-111111111111',
    username: 'mahmoud',
    email: 'mahmoud@veltrix.local',
    display_name: 'Mahmoud Almbaidin',
    status: 'active',
    is_platform_admin: false,
    must_change_password: false,
    job_title: 'CEO',
    preferences: { theme: 'dark' },
  },
  session: { expires_at: '2026-08-12T00:00:00Z' },
}

describe('settingsService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates the profile via PATCH /auth/me and parses the session', async () => {
    client.patch.mockResolvedValue(AUTH_RESPONSE)
    const session = await settingsService.updateProfile({ job_title: 'CEO' })
    expect(client.patch).toHaveBeenCalledWith('/auth/me', { job_title: 'CEO' })
    expect(session.user.jobTitle).toBe('CEO')
    expect(session.user.preferences).toEqual({ theme: 'dark' })
  })

  it('merges a preferences-only update through the same endpoint', async () => {
    client.patch.mockResolvedValue(AUTH_RESPONSE)
    await settingsService.updatePreferences({ density: 'compact' })
    expect(client.patch).toHaveBeenCalledWith('/auth/me', { preferences: { density: 'compact' } })
  })

  it('maps the active session list', async () => {
    client.get.mockResolvedValue({
      sessions: [
        {
          id: 's1',
          created_at: '2026-08-10T00:00:00Z',
          last_seen_at: '2026-08-12T00:00:00Z',
          access_expires_at: '2026-08-12T01:00:00Z',
          refresh_expires_at: '2026-08-19T00:00:00Z',
          current: true,
        },
      ],
    })
    const sessions = await settingsService.listSessions()
    expect(sessions).toHaveLength(1)
    expect(sessions[0]).toMatchObject({ id: 's1', current: true })
  })

  it('reports how many other sessions were revoked', async () => {
    client.post.mockResolvedValue({ revoked: 3 })
    await expect(settingsService.revokeOtherSessions()).resolves.toBe(3)
    expect(client.post).toHaveBeenCalledWith('/auth/sessions/revoke-others')
  })

  it('rejects a non-image avatar before any upload', async () => {
    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await expect(settingsService.uploadAvatar(file)).rejects.toThrow(/PNG or JPEG/)
    expect(client.uploadRaw).not.toHaveBeenCalled()
  })

  it('rejects an oversized avatar before any upload', async () => {
    const big = new File([new Uint8Array(6 * 1024 * 1024)], 'big.png', { type: 'image/png' })
    await expect(settingsService.uploadAvatar(big)).rejects.toThrow(/5 MB/)
    expect(client.uploadRaw).not.toHaveBeenCalled()
  })

  it('streams a valid avatar with the file-name and content-type headers', async () => {
    client.uploadRaw.mockResolvedValue(AUTH_RESPONSE)
    const png = new File([new Uint8Array(16)], 'avatar.png', { type: 'image/png' })
    await settingsService.uploadAvatar(png)
    expect(client.uploadRaw).toHaveBeenCalledWith(
      '/auth/me/avatar',
      png,
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-File-Name': 'avatar.png', 'Content-Type': 'image/png' }),
      }),
    )
  })
})
