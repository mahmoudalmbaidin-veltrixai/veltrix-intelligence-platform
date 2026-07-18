/**
 * Platform store: the authenticated context (user, org, workspace, role,
 * permissions, entitlements, feature flags). Development role-switching lets
 * reviewers see permission/entitlement-aware UI without a real backend.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type {
  AuthContext, Entitlement, EntitlementKey, FeatureFlagKey,
  Organization, Permission, RoleKey, UserProfile, Workspace,
} from '@/shared/types/identity'
import { hasPermission, permissionsFor } from '@/shared/permissions/roles'
import { LocalStore } from '@/shared/lib/mock'
import { invalidateQueries } from '@/shared/lib/query'

const USER: UserProfile = {
  id: 'usr_veltrix_01',
  name: 'Mahmoud Almbaidin',
  email: 'mahmoud.almbaidin@shabakkatksa.com',
  avatarColor: '#6d5efc',
  jobTitle: 'Principal Data Platform Lead',
  timezone: 'Asia/Riyadh',
  locale: 'en-US',
}

const ORGS: Organization[] = [
  { id: 'org_veltrix', name: 'Veltrix Global', slug: 'veltrix', status: 'active', plan: 'enterprise' },
  { id: 'org_northwind', name: 'Northwind Trading', slug: 'northwind', status: 'trial', plan: 'trial' },
]

const WORKSPACES: Workspace[] = [
  { id: 'ws_analytics', orgId: 'org_veltrix', name: 'Analytics', slug: 'analytics', archived: false },
  { id: 'ws_revops', orgId: 'org_veltrix', name: 'Revenue Ops', slug: 'revops', archived: false },
  { id: 'ws_platform', orgId: 'org_veltrix', name: 'Platform', slug: 'platform', archived: false },
  { id: 'ws_sandbox', orgId: 'org_northwind', name: 'Sandbox', slug: 'sandbox', archived: false },
]

const ENTITLEMENTS: Record<'enterprise' | 'trial', Entitlement[]> = {
  enterprise: [
    { key: 'pipelines', enabled: true, limit: 500, used: 42 },
    { key: 'dashboards', enabled: true, limit: 1000, used: 128 },
    { key: 'ai-assistant', enabled: true },
    { key: 'ai-agents', enabled: true, limit: 50, used: 6 },
    { key: 'automation', enabled: true },
    { key: 'developer-api', enabled: true },
    { key: 'marketplace', enabled: true },
    { key: 'advanced-governance', enabled: true },
    { key: 'sso', enabled: true },
  ],
  trial: [
    { key: 'pipelines', enabled: true, limit: 5, used: 2 },
    { key: 'dashboards', enabled: true, limit: 10, used: 3 },
    { key: 'ai-assistant', enabled: true },
    { key: 'ai-agents', enabled: false },
    { key: 'automation', enabled: false },
    { key: 'developer-api', enabled: true, limit: 1, used: 0 },
    { key: 'marketplace', enabled: false },
    { key: 'advanced-governance', enabled: false },
    { key: 'sso', enabled: false },
  ],
}

const DEFAULT_FLAGS: Record<FeatureFlagKey, boolean> = {
  'pipeline-python-node': true,
  'dashboard-map-widget': true,
  'insights-nlq': true,
  'ai-agents-beta': true,
  'marketplace-extensions': true,
  'report-approvals': true,
}

const prefStore = new LocalStore<{ role: RoleKey; orgId: string; wsId: string }>('vip.platform.prefs')

export const usePlatformStore = defineStore('platform', () => {
  const saved = prefStore.read({ role: 'workspace-admin', orgId: 'org_veltrix', wsId: 'ws_analytics' })

  const user = ref<UserProfile>(USER)
  const role = ref<RoleKey>(saved.role)
  const orgId = ref<string>(saved.orgId)
  const workspaceId = ref<string>(saved.wsId)
  const featureFlags = ref<Record<FeatureFlagKey, boolean>>({ ...DEFAULT_FLAGS })

  const organizations = computed(() => ORGS)
  const organization = computed(() => ORGS.find((o) => o.id === orgId.value) ?? ORGS[0])
  const workspaces = computed(() => WORKSPACES.filter((w) => w.orgId === orgId.value))
  const workspace = computed(
    () => WORKSPACES.find((w) => w.id === workspaceId.value) ?? workspaces.value[0],
  )
  const permissions = computed(() => permissionsFor(role.value))
  const entitlements = computed<Entitlement[]>(() =>
    organization.value.plan === 'enterprise' ? ENTITLEMENTS.enterprise : ENTITLEMENTS.trial,
  )

  const authContext = computed<AuthContext>(() => ({
    user: user.value,
    organization: organization.value,
    workspace: workspace.value,
    role: role.value,
    permissions: permissions.value,
    entitlements: entitlements.value,
    featureFlags: featureFlags.value,
  }))

  function persist() {
    prefStore.write({ role: role.value, orgId: orgId.value, wsId: workspaceId.value })
  }

  function can(permission?: Permission): boolean {
    return hasPermission(permissions.value, permission)
  }

  function entitled(key: EntitlementKey): boolean {
    return entitlements.value.find((e) => e.key === key)?.enabled ?? false
  }

  function entitlement(key: EntitlementKey): Entitlement | undefined {
    return entitlements.value.find((e) => e.key === key)
  }

  function flagEnabled(key: FeatureFlagKey): boolean {
    return featureFlags.value[key] ?? false
  }

  function setRole(r: RoleKey) {
    role.value = r
    persist()
  }

  /**
   * Tenant scoping: switching org/workspace invalidates all cached server
   * state so no data leaks across tenants. Live adapters also re-issue requests
   * with the new X-Organization-Id / X-Workspace-Id headers.
   */
  function switchOrg(id: string) {
    orgId.value = id
    const firstWs = WORKSPACES.find((w) => w.orgId === id)
    if (firstWs) workspaceId.value = firstWs.id
    persist()
    invalidateQueries('')
  }

  function switchWorkspace(id: string) {
    workspaceId.value = id
    persist()
    invalidateQueries('')
  }

  function toggleFlag(key: FeatureFlagKey, value?: boolean) {
    featureFlags.value[key] = value ?? !featureFlags.value[key]
  }

  return {
    user, role, orgId, workspaceId, featureFlags,
    organizations, organization, workspaces, workspace,
    permissions, entitlements, authContext,
    can, entitled, entitlement, flagEnabled,
    setRole, switchOrg, switchWorkspace, toggleFlag,
  }
})
