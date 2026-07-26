/** Authenticated identity plus server-validated organization/workspace navigation context. */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type {
  AuthContext,
  Entitlement,
  EntitlementKey,
  FeatureFlagKey,
  Organization,
  Permission,
  RoleKey,
  UserProfile,
  Workspace,
} from '@/shared/types/identity'
import type { AuthenticatedUser } from '@/shared/services/auth'
import {
  tenancyService,
  type AuthorizedOrganizationDto,
  type AuthorizedWorkspaceDto,
} from '@/shared/services/tenancy/apiTenancyService'
import { useAuthorizationStore } from '@/shared/stores/authorization'
import { LocalStore, setStorageScope } from '@/shared/lib/mock'
import { invalidateQueries } from '@/shared/lib/query'
import { ApiError } from '@/shared/types/api'

export type TenancyStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

const EMPTY_USER: UserProfile = {
  id: '',
  name: '',
  email: '',
  avatarColor: '#6d5efc',
  jobTitle: '',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  locale: navigator.language || 'en-US',
}

interface TenantPreference {
  userId: string
  orgId: string | null
  wsId: string | null
}

const prefStore = new LocalStore<TenantPreference>('vip.tenancy.preference')

function mapOrganization(value: AuthorizedOrganizationDto): Organization {
  return {
    id: value.id,
    name: value.name,
    slug: value.slug,
    status: value.status,
    membershipRole: value.membership.role,
    // Billing is intentionally outside B2; this remains a UI capability default, not authorization.
    plan: 'enterprise',
  }
}

function mapWorkspace(value: AuthorizedWorkspaceDto): Workspace {
  return {
    id: value.id,
    orgId: value.organization_id,
    name: value.name,
    slug: value.slug,
    status: value.status,
    isDefault: value.is_default,
  }
}

export const usePlatformStore = defineStore('platform', () => {
  const authorization = useAuthorizationStore()
  const user = ref<UserProfile>({ ...EMPTY_USER })
  const organizations = ref<Organization[]>([])
  const workspaces = ref<Workspace[]>([])
  const orgId = ref<string | null>(null)
  const workspaceId = ref<string | null>(null)
  const status = ref<TenancyStatus>('idle')
  const initialized = ref(false)
  const error = ref<ApiError | null>(null)
  let bootstrapPromise: Promise<void> | null = null

  const organization = computed(() => organizations.value.find((item) => item.id === orgId.value) ?? null)
  const workspace = computed(() => workspaces.value.find((item) => item.id === workspaceId.value) ?? null)
  const role = computed<RoleKey>(() => authorization.role || organization.value?.membershipRole || '')
  const permissions = computed(() => authorization.permissions)
  const entitlements = computed<Entitlement[]>(() =>
    authorization.entitlements.map((key) => {
      const quota = authorization.quota(`${key}.max`)
      return { key, enabled: true, limit: quota?.limit, used: quota?.used }
    }),
  )
  const featureFlags = computed<Record<FeatureFlagKey, boolean>>(() => authorization.features)

  const authContext = computed<AuthContext | null>(() => {
    if (!organization.value || !workspace.value) return null
    return {
      user: user.value,
      organization: organization.value,
      workspace: workspace.value,
      role: role.value,
      permissions: permissions.value,
      entitlements: entitlements.value,
      featureFlags: featureFlags.value,
    }
  })

  function applyScope(): void {
    setStorageScope(`${user.value.id || 'anonymous'}:${orgId.value ?? 'none'}:${workspaceId.value ?? 'none'}`)
  }

  function persist(): void {
    prefStore.write({ userId: user.value.id, orgId: orgId.value, wsId: workspaceId.value })
  }

  function invalidateTenantState(): void {
    invalidateQueries('')
    applyScope()
  }

  async function fetchWorkspaces(organizationId: string, preferredWorkspaceId?: string | null): Promise<void> {
    workspaces.value = (await tenancyService.listWorkspaces(organizationId)).map(mapWorkspace)
    const selected = workspaces.value.find((item) => item.id === preferredWorkspaceId)
    workspaceId.value =
      selected?.id ?? workspaces.value.find((item) => item.isDefault)?.id ?? workspaces.value[0]?.id ?? null
  }

  async function bootstrapTenancy(force = false): Promise<void> {
    if (bootstrapPromise) return bootstrapPromise
    if (initialized.value && !force) return
    status.value = 'loading'
    error.value = null
    bootstrapPromise = (async () => {
      try {
        const saved = prefStore.read({ userId: '', orgId: null, wsId: null })
        organizations.value = (await tenancyService.listOrganizations()).map(mapOrganization)
        const preferredOrg = saved.userId === user.value.id ? saved.orgId : null
        orgId.value =
          organizations.value.find((item) => item.id === preferredOrg)?.id ?? organizations.value[0]?.id ?? null
        if (orgId.value) {
          await fetchWorkspaces(orgId.value, saved.userId === user.value.id ? saved.wsId : null)
          status.value = 'ready'
        } else {
          workspaces.value = []
          workspaceId.value = null
          status.value = 'empty'
        }
        initialized.value = true
        persist()
        invalidateTenantState()
        if (orgId.value && workspaceId.value) await authorization.bootstrap(true)
      } catch (cause) {
        organizations.value = []
        workspaces.value = []
        orgId.value = null
        workspaceId.value = null
        error.value = ApiError.from(cause)
        status.value = 'error'
        initialized.value = true
        invalidateTenantState()
      } finally {
        bootstrapPromise = null
      }
    })()
    return bootstrapPromise
  }

  async function switchOrg(id: string): Promise<void> {
    const target = organizations.value.find((item) => item.id === id)
    if (!target || target.id === orgId.value) return
    orgId.value = target.id
    workspaceId.value = null
    workspaces.value = []
    authorization.clear()
    persist()
    invalidateTenantState()
    try {
      await fetchWorkspaces(target.id)
      status.value = 'ready'
      persist()
      invalidateTenantState()
      if (workspaceId.value) await authorization.bootstrap(true)
    } catch (cause) {
      error.value = ApiError.from(cause)
      await bootstrapTenancy(true)
    }
  }

  async function switchWorkspace(id: string): Promise<void> {
    if (!workspaces.value.some((item) => item.id === id) || id === workspaceId.value) return
    workspaceId.value = id
    authorization.clear()
    persist()
    invalidateTenantState()
    await authorization.bootstrap(true)
  }

  function hydrateAuthenticatedUser(authenticatedUser: AuthenticatedUser): void {
    if (user.value.id && user.value.id !== authenticatedUser.id) clearTenantContext()
    user.value = {
      ...user.value,
      id: authenticatedUser.id,
      email: authenticatedUser.email,
      name: authenticatedUser.displayName,
    }
  }

  function clearTenantContext(): void {
    organizations.value = []
    workspaces.value = []
    orgId.value = null
    workspaceId.value = null
    initialized.value = false
    status.value = 'idle'
    error.value = null
    authorization.clear()
    prefStore.clear()
    invalidateTenantState()
  }

  function can(permission?: Permission): boolean {
    return authorization.can(permission)
  }
  function entitled(key: EntitlementKey): boolean {
    return authorization.entitled(key)
  }
  function entitlement(key: EntitlementKey): Entitlement | undefined {
    return entitlements.value.find((item) => item.key === key)
  }
  function flagEnabled(key: FeatureFlagKey): boolean {
    return authorization.flagEnabled(key)
  }

  return {
    user,
    role,
    orgId,
    workspaceId,
    organizations,
    workspaces,
    organization,
    workspace,
    permissions,
    entitlements,
    authContext,
    featureFlags,
    status,
    initialized,
    error,
    can,
    entitled,
    entitlement,
    flagEnabled,
    bootstrapTenancy,
    fetchWorkspaces,
    switchOrg,
    switchWorkspace,
    hydrateAuthenticatedUser,
    clearContext: clearTenantContext,
    clearTenantContext,
    applyScope,
  }
})
