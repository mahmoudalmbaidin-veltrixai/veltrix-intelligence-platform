/**
 * Mock authentication adapter. Simulates cookie-session bootstrap, login,
 * logout and refresh with realistic latency, persisting only a non-sensitive
 * session marker (never a real credential) to localStorage.
 */
import type { AuthService, LoginCredentials, Session } from './types'
import type { AuthContext } from '@/shared/types/identity'
import { permissionsFor } from '@/shared/permissions/roles'
import { LocalStore, latency, isoAhead } from '@/shared/lib/mock'
import { ApiError } from '@/shared/types/api'

interface StoredSession {
  active: boolean
  email: string
  expiresAt: string
}

const store = new LocalStore<StoredSession | null>('vip.auth.session')

function defaultContext(email: string): AuthContext {
  const role = 'workspace-admin' as const
  return {
    user: {
      id: 'usr_veltrix_01',
      name: 'Mahmoud Almbaidin',
      email,
      avatarColor: '#6d5efc',
      jobTitle: 'Principal Data Platform Lead',
      timezone: 'Asia/Riyadh',
      locale: 'en-US',
    },
    organization: { id: 'org_veltrix', name: 'Veltrix Global', slug: 'veltrix', status: 'active', plan: 'enterprise' },
    workspace: { id: 'ws_analytics', orgId: 'org_veltrix', name: 'Analytics', slug: 'analytics', archived: false },
    role,
    permissions: permissionsFor(role),
    entitlements: [],
    featureFlags: {
      'pipeline-python-node': true,
      'dashboard-map-widget': true,
      'insights-nlq': true,
      'ai-agents-beta': true,
      'marketplace-extensions': true,
      'report-approvals': true,
    },
  }
}

function sessionFrom(email: string): Session {
  const expiresAt = isoAhead(60 * 8)
  return { token: undefined /* cookie-session in mock */, expiresAt, context: defaultContext(email) }
}

export const mockAuthService: AuthService = {
  async bootstrap() {
    await latency(120, 280)
    const stored = store.read(null)
    if (!stored?.active) return null
    if (new Date(stored.expiresAt).getTime() < Date.now()) {
      store.write(null)
      return null
    }
    return sessionFrom(stored.email)
  },

  async login({ email, password }: LoginCredentials) {
    await latency(300, 700)
    if (!email || !password) {
      throw new ApiError('validation', 'Email and password are required.', {
        fieldErrors: [
          ...(!email ? [{ field: 'email', message: 'Email is required.' }] : []),
          ...(!password ? [{ field: 'password', message: 'Password is required.' }] : []),
        ],
      })
    }
    const session = sessionFrom(email)
    store.write({ active: true, email, expiresAt: session.expiresAt })
    return session
  },

  async logout() {
    await latency(80, 160)
    store.write(null)
  },

  async currentUser() {
    await latency(80, 200)
    const stored = store.read(null)
    return stored?.active ? defaultContext(stored.email) : null
  },

  async refresh() {
    await latency(120, 260)
    const stored = store.read(null)
    if (!stored?.active) return null
    const session = sessionFrom(stored.email)
    store.write({ active: true, email: stored.email, expiresAt: session.expiresAt })
    return session
  },
}

/** Dev convenience: seed an active session so mock mode boots "logged in". */
export function seedMockSession(email = 'mahmoud.almbaidin@shabakkatksa.com'): void {
  if (store.read(null) == null) {
    store.write({ active: true, email, expiresAt: isoAhead(60 * 8) })
  }
}
