import type { Permission, PermissionMatcher, RoleDefinition, RoleKey } from '@/shared/types/identity'

const ALL_READ: Permission[] = [
  'connection:read', 'pipeline:read', 'dataset:read', 'semantic:read',
  'dashboard:read', 'report:read', 'insight:read', 'notification:read',
  'usage:read', 'marketplace:read',
]

export const ROLES: Record<RoleKey, RoleDefinition> = {
  'platform-admin': {
    key: 'platform-admin',
    label: 'Platform Administrator',
    description: 'Full multi-tenant platform access.',
    permissions: ['*'],
  },
  'org-owner': {
    key: 'org-owner',
    label: 'Organization Owner',
    description: 'Owns the organization, billing and governance.',
    permissions: ['*'],
  },
  'org-admin': {
    key: 'org-admin',
    label: 'Organization Administrator',
    description: 'Administers org members, roles and settings.',
    permissions: [
      ...ALL_READ, 'admin:org', 'admin:workspace', 'governance:read', 'governance:write',
      'featureflag:read', 'billing:read', 'audit:read', 'ai:use', 'ai:configure',
      'automation:read', 'automation:write', 'developer:read', 'developer:write',
      'connection:write', 'pipeline:write', 'pipeline:run', 'pipeline:publish',
      'dashboard:write', 'dashboard:publish', 'dashboard:share', 'report:write',
      'dataset:write', 'semantic:write', 'insight:write', 'marketplace:install',
    ],
  },
  'workspace-admin': {
    key: 'workspace-admin',
    label: 'Workspace Administrator',
    description: 'Administers a single workspace and its resources.',
    permissions: [
      ...ALL_READ, 'admin:workspace', 'connection:write', 'pipeline:write', 'pipeline:run',
      'pipeline:publish', 'pipeline:delete', 'dataset:write', 'dataset:certify',
      'semantic:write', 'semantic:publish', 'dashboard:write', 'dashboard:publish',
      'dashboard:share', 'report:write', 'report:approve', 'report:publish',
      'insight:write', 'ai:use', 'ai:configure', 'automation:read', 'automation:write',
      'automation:approve', 'developer:read', 'developer:write', 'marketplace:install',
    ],
  },
  'data-engineer': {
    key: 'data-engineer',
    label: 'Data Engineer',
    description: 'Builds connections, pipelines and datasets.',
    permissions: [
      ...ALL_READ, 'connection:write', 'connection:delete', 'pipeline:write',
      'pipeline:run', 'pipeline:publish', 'pipeline:delete', 'dataset:write',
      'dataset:certify', 'semantic:write', 'automation:read', 'automation:write',
      'ai:use', 'developer:read',
    ],
  },
  analyst: {
    key: 'analyst',
    label: 'Analyst',
    description: 'Explores data, builds dashboards and insights.',
    permissions: [
      ...ALL_READ, 'dashboard:write', 'dashboard:publish', 'dashboard:share',
      'insight:write', 'semantic:read', 'ai:use', 'report:read',
    ],
  },
  'report-author': {
    key: 'report-author',
    label: 'Report Author',
    description: 'Authors and submits reports for approval.',
    permissions: [...ALL_READ, 'report:write', 'report:publish', 'dashboard:write', 'ai:use'],
  },
  'business-viewer': {
    key: 'business-viewer',
    label: 'Business Viewer',
    description: 'Views published dashboards, reports and insights.',
    permissions: [...ALL_READ, 'ai:use'],
  },
  developer: {
    key: 'developer',
    label: 'Developer',
    description: 'Manages API keys, webhooks and integrations.',
    permissions: [...ALL_READ, 'developer:read', 'developer:write', 'marketplace:read', 'marketplace:install'],
  },
}

export function permissionsFor(role: RoleKey): PermissionMatcher[] {
  const def = ROLES[role]
  return def.permissions as PermissionMatcher[]
}

export function hasPermission(perms: PermissionMatcher[], required: Permission | undefined): boolean {
  if (!required) return true
  if (perms.includes('*')) return true
  return perms.includes(required)
}
