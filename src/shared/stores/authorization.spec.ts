import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const governance = vi.hoisted(() => ({ authorizationContext: vi.fn() }))
vi.mock('@/shared/services/governance/apiGovernanceService', () => ({ governanceService: governance }))

import { useAuthorizationStore } from './authorization'

const context = {
  user_id: 'user',
  organization_id: 'organization',
  workspace_id: 'workspace',
  organization_role: 'organization_member',
  workspace_role: 'viewer',
  permissions: ['workspace.read', 'dashboard.read'],
  features: { dashboard_studio: false },
  entitlements: ['dashboard_studio'],
  quotas: { 'dashboards.max': { key: 'dashboards.max', limit: 10, used: 9, remaining: 1, hard: true } },
}

describe('authorization store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    governance.authorizationContext.mockReset().mockResolvedValue(context)
  })

  it('bootstraps only backend-resolved governance state', async () => {
    const store = useAuthorizationStore()
    await store.bootstrap()
    expect(store.role).toBe('viewer')
    expect(store.can('dashboard.read')).toBe(true)
    expect(store.can('dashboard.update')).toBe(false)
    expect(store.flagEnabled('dashboard_studio')).toBe(false)
    expect(store.entitled('dashboard_studio')).toBe(true)
    expect(store.quotaAvailable('dashboards.max')).toBe(true)
    expect(store.quotaAvailable('dashboards.max', 2)).toBe(false)
  })

  it('clears all authorization state when tenant or session changes', async () => {
    const store = useAuthorizationStore()
    await store.bootstrap()
    store.clear()
    expect(store.context).toBeNull()
    expect(store.can('workspace.read')).toBe(false)
    expect(store.status).toBe('idle')
  })
})
