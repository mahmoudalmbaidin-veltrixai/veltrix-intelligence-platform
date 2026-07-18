/**
 * Identity, tenancy and authorization contracts.
 * These mirror the shape the backend is expected to return.
 */

export type Id = string

export type RoleKey =
  | 'platform-admin'
  | 'org-owner'
  | 'org-admin'
  | 'workspace-admin'
  | 'data-engineer'
  | 'analyst'
  | 'report-author'
  | 'business-viewer'
  | 'developer'

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
export type Permission =
  | 'connection:read'
  | 'connection:write'
  | 'connection:delete'
  | 'pipeline:read'
  | 'pipeline:write'
  | 'pipeline:run'
  | 'pipeline:publish'
  | 'pipeline:delete'
  | 'dataset:read'
  | 'dataset:write'
  | 'dataset:certify'
  | 'semantic:read'
  | 'semantic:write'
  | 'semantic:publish'
  | 'dashboard:read'
  | 'dashboard:write'
  | 'dashboard:publish'
  | 'dashboard:share'
  | 'report:read'
  | 'report:write'
  | 'report:approve'
  | 'report:publish'
  | 'insight:read'
  | 'insight:write'
  | 'ai:use'
  | 'ai:configure'
  | 'automation:read'
  | 'automation:write'
  | 'automation:approve'
  | 'notification:read'
  | 'audit:read'
  | 'usage:read'
  | 'marketplace:read'
  | 'marketplace:install'
  | 'developer:read'
  | 'developer:write'
  | 'billing:read'
  | 'billing:manage'
  | 'admin:platform'
  | 'admin:org'
  | 'admin:workspace'
  | 'governance:read'
  | 'governance:write'
  | 'featureflag:read'
  | 'featureflag:write'

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

export type TenantStatus = 'trial' | 'active' | 'suspended' | 'disabled' | 'pending-deletion'

export interface Organization {
  id: Id
  name: string
  slug: string
  status: TenantStatus
  plan: PlanKey
}

export interface Workspace {
  id: Id
  orgId: Id
  name: string
  slug: string
  archived: boolean
}

export type PlanKey = 'trial' | 'team' | 'business' | 'enterprise'

/** Entitlement keys gate features behind plans/limits. */
export type EntitlementKey =
  | 'pipelines'
  | 'dashboards'
  | 'ai-assistant'
  | 'ai-agents'
  | 'automation'
  | 'developer-api'
  | 'marketplace'
  | 'advanced-governance'
  | 'sso'

export interface Entitlement {
  key: EntitlementKey
  enabled: boolean
  /** Optional usage cap; undefined means unlimited within the plan. */
  limit?: number
  used?: number
}

export type FeatureFlagKey =
  | 'pipeline-python-node'
  | 'dashboard-map-widget'
  | 'insights-nlq'
  | 'ai-agents-beta'
  | 'marketplace-extensions'
  | 'report-approvals'

export interface AuthContext {
  user: UserProfile
  organization: Organization
  workspace: Workspace
  role: RoleKey
  permissions: PermissionMatcher[]
  entitlements: Entitlement[]
  featureFlags: Record<FeatureFlagKey, boolean>
}
