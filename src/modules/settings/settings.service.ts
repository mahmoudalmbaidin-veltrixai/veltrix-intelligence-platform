/**
 * Self-service account settings adapter — profile, preferences, sessions and
 * avatar — backed by the real /auth endpoints. Every mutation returns the fresh
 * session so callers can re-hydrate the platform store without a second request.
 */
import { apiClient } from '@/shared/lib/apiClient'
import { parseSession } from '@/shared/services/auth/apiAuthService'
import type { Session } from '@/shared/services/auth'

export interface ProfileUpdatePayload {
  display_name?: string
  job_title?: string | null
  department?: string | null
  phone?: string | null
  locale?: string | null
  timezone?: string | null
  preferences?: Record<string, unknown>
}

export interface ActiveSession {
  id: string
  createdAt: string
  lastSeenAt: string
  accessExpiresAt: string
  refreshExpiresAt: string
  current: boolean
}

interface ApiSession {
  id: string
  created_at: string
  last_seen_at: string
  access_expires_at: string
  refresh_expires_at: string
  current: boolean
}

const MAX_AVATAR_BYTES = 5 * 1024 * 1024
const ACCEPTED_AVATAR_TYPES = ['image/png', 'image/jpeg']

export const settingsService = {
  async updateProfile(payload: ProfileUpdatePayload): Promise<Session> {
    return parseSession(await apiClient.patch<unknown>('/auth/me', payload))
  },

  /** Convenience wrapper for preference-only updates (theme, density, etc.). */
  async updatePreferences(preferences: Record<string, unknown>): Promise<Session> {
    return parseSession(await apiClient.patch<unknown>('/auth/me', { preferences }))
  },

  async listSessions(): Promise<ActiveSession[]> {
    const data = await apiClient.get<{ sessions: ApiSession[] }>('/auth/sessions')
    return data.sessions.map((s) => ({
      id: s.id,
      createdAt: s.created_at,
      lastSeenAt: s.last_seen_at,
      accessExpiresAt: s.access_expires_at,
      refreshExpiresAt: s.refresh_expires_at,
      current: s.current,
    }))
  },

  async revokeSession(id: string): Promise<void> {
    await apiClient.delete<unknown>(`/auth/sessions/${id}`)
  },

  async revokeOtherSessions(): Promise<number> {
    const data = await apiClient.post<{ revoked: number }>('/auth/sessions/revoke-others')
    return data.revoked
  },

  /** Validates client-side, then streams the raw image to the avatar endpoint. */
  async uploadAvatar(file: File): Promise<Session> {
    if (!ACCEPTED_AVATAR_TYPES.includes(file.type)) {
      throw new Error('Please choose a PNG or JPEG image.')
    }
    if (file.size > MAX_AVATAR_BYTES) {
      throw new Error('The image must be 5 MB or smaller.')
    }
    return parseSession(
      await apiClient.uploadRaw<unknown>('/auth/me/avatar', file, {
        headers: { 'X-File-Name': file.name || 'avatar.png', 'Content-Type': file.type },
      }),
    )
  },

  async removeAvatar(): Promise<Session> {
    return parseSession(await apiClient.delete<unknown>('/auth/me/avatar'))
  },

  /**
   * Fetch the avatar through the credentialed API client (works cross-origin
   * where a bare <img> src would not send the session cookie) and return an
   * object URL. Callers own revoking the previous URL.
   */
  async fetchAvatarObjectUrl(): Promise<string | null> {
    try {
      const blob = await apiClient.download('/auth/me/avatar')
      return URL.createObjectURL(blob)
    } catch {
      return null
    }
  },
}
