import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const tenancy = vi.hoisted(() => ({
  listOrganizations: vi.fn(),
  listWorkspaces: vi.fn(),
}))
const governance = vi.hoisted(() => ({
  authorizationContext: vi.fn(),
}))
vi.mock('@/shared/services/tenancy/apiTenancyService', () => ({ tenancyService: tenancy }))
vi.mock('@/shared/services/governance/apiGovernanceService', () => ({ governanceService: governance }))

import { currentStorageScope } from '@/shared/lib/mock'
import { usePlatformStore } from './platform'

const alpha = {
  id: '00000000-0000-4000-8000-000000000001',
  name: 'Alpha',
  slug: 'alpha',
  status: 'active' as const,
  membership: { role: 'owner' as const, status: 'active' as const },
}
const beta = {
  id: '00000000-0000-4000-8000-000000000002',
  name: 'Beta',
  slug: 'beta',
  status: 'active' as const,
  membership: { role: 'member' as const, status: 'active' as const },
}
const alphaOne = {
  id: '10000000-0000-4000-8000-000000000001',
  organization_id: alpha.id,
  name: 'Alpha One',
  slug: 'one',
  status: 'active' as const,
  is_default: true,
}
const betaOne = {
  id: '20000000-0000-4000-8000-000000000001',
  organization_id: beta.id,
  name: 'Beta One',
  slug: 'one',
  status: 'active' as const,
  is_default: true,
}

describe('server-backed tenancy store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
    tenancy.listOrganizations.mockResolvedValue([alpha, beta])
    tenancy.listWorkspaces.mockImplementation((organizationId: string) =>
      Promise.resolve(organizationId === alpha.id ? [alphaOne] : [betaOne]),
    )
    governance.authorizationContext.mockResolvedValue({
      user_id: 'user-a',
      organization_id: alpha.id,
      workspace_id: alphaOne.id,
      organization_role: 'organization_owner',
      workspace_role: 'workspace_admin',
      permissions: ['workspace.read'],
      features: { dashboard_studio: true },
      entitlements: ['dashboard_studio'],
      quotas: {},
    })
  })

  it('loads only backend-authorized organizations and workspaces', async () => {
    const store = usePlatformStore()
    store.hydrateAuthenticatedUser({ id: 'user-a', email: 'a@test', displayName: 'User A', status: 'active' })
    await store.bootstrapTenancy()
    expect(store.organizations.map((item) => item.name)).toEqual(['Alpha', 'Beta'])
    expect(store.organization?.id).toBe(alpha.id)
    expect(store.workspace?.id).toBe(alphaOne.id)
    expect(store.initialized).toBe(true)
  })

  it('clears the stale workspace before changing organization and segregates scope', async () => {
    const store = usePlatformStore()
    store.hydrateAuthenticatedUser({ id: 'user-a', email: 'a@test', displayName: 'User A', status: 'active' })
    await store.bootstrapTenancy()
    const switching = store.switchOrg(beta.id)
    expect(store.workspaceId).toBeNull()
    await switching
    expect(store.workspace?.id).toBe(betaOne.id)
    expect(currentStorageScope()).toContain(`${beta.id}:${betaOne.id}`)
  })

  it('discards unauthorized persisted selections', async () => {
    localStorage.setItem(
      'vip.tenancy.preference',
      JSON.stringify({ userId: 'user-a', orgId: 'not-authorized', wsId: 'stale-workspace' }),
    )
    const store = usePlatformStore()
    store.hydrateAuthenticatedUser({ id: 'user-a', email: 'a@test', displayName: 'User A', status: 'active' })
    await store.bootstrapTenancy()
    expect(store.organization?.id).toBe(alpha.id)
    expect(store.workspace?.id).toBe(alphaOne.id)
  })

  it('does not reuse another user preference and clears all tenant state on logout', async () => {
    localStorage.setItem(
      'vip.tenancy.preference',
      JSON.stringify({ userId: 'other-user', orgId: beta.id, wsId: betaOne.id }),
    )
    const store = usePlatformStore()
    store.hydrateAuthenticatedUser({ id: 'user-a', email: 'a@test', displayName: 'User A', status: 'active' })
    await store.bootstrapTenancy()
    expect(store.organization?.id).toBe(alpha.id)
    store.clearTenantContext()
    expect(store.organizations).toEqual([])
    expect(store.workspaces).toEqual([])
    expect(store.organization).toBeNull()
    expect(localStorage.getItem('vip.tenancy.preference')).toBeNull()
  })

  it('renders a valid empty tenancy state', async () => {
    tenancy.listOrganizations.mockResolvedValue([])
    const store = usePlatformStore()
    store.hydrateAuthenticatedUser({ id: 'user-a', email: 'a@test', displayName: 'User A', status: 'active' })
    await store.bootstrapTenancy()
    expect(store.status).toBe('empty')
    expect(store.organization).toBeNull()
    expect(store.workspace).toBeNull()
  })
})
