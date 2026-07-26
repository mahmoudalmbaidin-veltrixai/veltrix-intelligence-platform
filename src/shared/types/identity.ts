/**
 * Identity, tenancy and authorization contracts.
 * These mirror the shape the backend is expected to return.
 */

export type Id = string

export type RoleKey = string

export interface RoleDefinition {
  key: RoleKey
  label: string
  description: string
  /** Permissions granted by this role (or '*' for full access). */
  permissions: Permission[] | ['*']
}

/**
 * Permission keys follow `domain:action` convention. Kept as a string union
 * for autocompletion while remaining open to backend-driven extension.
 */
export type Permission = string

export type PermissionMatcher = Permission | '*'

export interface UserProfile {
  id: Id
  name: string
  email: string
  avatarColor: string
  jobTitle: string
  timezone: string
  locale: string
}

export type TenantStatus = 'trial' | 'active' | 'suspended' | 'archived' | 'deleted' | 'disabled' | 'pending-deletion'

export interface Organization {
  id: Id
  name: string
  slug: string
  status: TenantStatus
  plan: PlanKey
  membershipRole: string
}

export interface Workspace {
  id: Id
  orgId: Id
  name: string
  slug: string
  status: 'active' | 'archived' | 'deleted'
  isDefault: boolean
}

export type PlanKey = 'trial' | 'team' | 'business' | 'enterprise'

/** Entitlement keys gate features behind plans/limits. */
export type EntitlementKey = string

export interface Entitlement {
  key: EntitlementKey
  enabled: boolean
  /** Optional usage cap; undefined means unlimited within the plan. */
  limit?: number
  used?: number
}

export type FeatureFlagKey = string

export interface AuthContext {
  user: UserProfile
  organization: Organization
  workspace: Workspace
  role: RoleKey
  permissions: PermissionMatcher[]
  entitlements: Entitlement[]
  featureFlags: Record<FeatureFlagKey, boolean>
}
