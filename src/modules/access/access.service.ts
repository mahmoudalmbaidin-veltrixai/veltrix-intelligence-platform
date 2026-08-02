/**
 * Live Enterprise permissions APIs: groups, resource sharing, principals, and
 * effective/simulated access. Permission management is security-critical and has
 * no offline mock — every call goes through the centralized {@link apiClient} to
 * the governed backend, which is the sole authorization decision point.
 */
import { apiClient } from '@/shared/lib/apiClient'

export interface Group {
  id: string
  name: string
  slug: string
  description: string
  workspace_id: string | null
  archived_at: string | null
  row_version: number
  member_count: number
  created_at: string
  updated_at: string
}

export interface GroupMember {
  user_id: string
  display_name: string
  email: string | null
  username: string
  added_at: string
}

export interface Principal {
  principal_type: 'user' | 'group'
  id: string
  label: string
  detail: string | null
  in_workspace: boolean
}

export interface ResourceEntry {
  id: string
  subject_type: 'user' | 'group'
  subject_id: string
  subject_label: string
  subject_detail: string | null
  access_level: string
  effect: 'allow' | 'deny'
  expires_at: string | null
  granted_by_user_id: string | null
  created_at: string
}

export interface ResourceTypeInfo {
  resource_type: string
  levels: string[]
}

export interface EffectiveAccess {
  resource_type: string
  resource_id: string
  user_id: string
  level: string | null
  allowed_levels: string[]
  source: string
  reason: string
}

export interface PermissionCatalogItem {
  key: string
  name: string
  description: string
  scope: string
  category: string
}

export interface Role {
  id: string
  name: string
  slug: string | null
  description: string
  scope: 'organization' | 'workspace'
  status: string
  is_system: boolean
  is_editable: boolean
  organization_id: string | null
  workspace_id: string | null
  priority: number
  permission_keys: string[]
  assignment_count: number
  row_version: number
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface RoleAssignment {
  id: string
  subject_type: 'user' | 'group'
  subject_id: string
  subject_label: string
  role_id: string
  role_name: string
  scope: string
  workspace_id: string | null
  created_at: string
}

export interface BulkResultItem {
  subject_id: string
  ok: boolean
  detail: string
}

export interface ResourceSearchItem {
  id: string
  name: string
  resource_type: string
  status: string | null
  owner_user_id: string | null
  workspace_id: string | null
  updated_at: string | null
}

const base = '/api/v1'

export const accessService = {
  listGroups(includeArchived = false): Promise<Group[]> {
    return apiClient.get<Group[]>(`${base}/groups`, { query: { include_archived: includeArchived } })
  },
  createGroup(name: string, description = ''): Promise<Group> {
    return apiClient.post<Group>(`${base}/groups`, { name, description })
  },
  getGroup(groupId: string): Promise<Group> {
    return apiClient.get<Group>(`${base}/groups/${encodeURIComponent(groupId)}`)
  },
  updateGroup(
    groupId: string,
    expectedVersion: number,
    changes: { name?: string; description?: string },
  ): Promise<Group> {
    return apiClient.patch<Group>(`${base}/groups/${encodeURIComponent(groupId)}`, {
      expected_version: expectedVersion,
      ...changes,
    })
  },
  archiveGroup(groupId: string, expectedVersion: number, archived: boolean): Promise<Group> {
    return apiClient.post<Group>(`${base}/groups/${encodeURIComponent(groupId)}/archive`, {
      expected_version: expectedVersion,
      archived,
    })
  },
  deleteGroup(groupId: string, expectedVersion: number): Promise<void> {
    return apiClient.delete<void>(`${base}/groups/${encodeURIComponent(groupId)}?expected_version=${expectedVersion}`)
  },
  listMembers(groupId: string): Promise<GroupMember[]> {
    return apiClient.get<GroupMember[]>(`${base}/groups/${encodeURIComponent(groupId)}/members`)
  },
  addMember(groupId: string, userId: string): Promise<void> {
    return apiClient.post<void>(`${base}/groups/${encodeURIComponent(groupId)}/members`, {
      user_id: userId,
    })
  },
  removeMember(groupId: string, userId: string): Promise<void> {
    return apiClient.delete<void>(`${base}/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(userId)}`)
  },
  searchPrincipals(query: string, limit = 50): Promise<Principal[]> {
    return apiClient.get<Principal[]>(`${base}/principals/search`, {
      query: { q: query, limit },
    })
  },
  listResourceTypes(): Promise<ResourceTypeInfo[]> {
    return apiClient.get<ResourceTypeInfo[]>(`${base}/resource-types`)
  },
  listResourceAccess(resourceType: string, resourceId: string): Promise<ResourceEntry[]> {
    return apiClient.get<ResourceEntry[]>(
      `${base}/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/access`,
    )
  },
  grantResourceAccess(
    resourceType: string,
    resourceId: string,
    grant: {
      subject_type: 'user' | 'group'
      subject_id: string
      access_level: string
      effect: 'allow' | 'deny'
      expires_at: string | null
    },
  ): Promise<ResourceEntry> {
    return apiClient.post<ResourceEntry>(
      `${base}/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/access`,
      grant,
    )
  },
  revokeResourceAccess(resourceType: string, resourceId: string, entryId: string): Promise<void> {
    return apiClient.delete<void>(
      `${base}/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/access/${encodeURIComponent(entryId)}`,
    )
  },
  effectiveAccess(resourceType: string, resourceId: string, userId?: string): Promise<EffectiveAccess> {
    return apiClient.get<EffectiveAccess>(
      `${base}/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/effective`,
      { query: userId ? { user_id: userId } : {} },
    )
  },
  simulateAccess(resourceType: string, resourceId: string, userId: string): Promise<EffectiveAccess> {
    return apiClient.post<EffectiveAccess>(
      `${base}/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/simulate`,
      { user_id: userId },
    )
  },
  searchResources(resourceType: string, query: string): Promise<ResourceSearchItem[]> {
    return apiClient.get<ResourceSearchItem[]>(`${base}/resources/${encodeURIComponent(resourceType)}/search`, {
      query: { q: query },
    })
  },

  // ---------------------------------------------------------------- roles
  permissionCatalog(): Promise<PermissionCatalogItem[]> {
    return apiClient.get<PermissionCatalogItem[]>(`${base}/permission-catalog`)
  },
  listRoles(options: { includeSystem?: boolean; includeArchived?: boolean; q?: string } = {}): Promise<Role[]> {
    // Custom-role CRUD lives under /custom-roles so it does not collide with the
    // legacy system-role catalog at GET /api/v1/roles used by Org Admin.
    return apiClient.get<Role[]>(`${base}/custom-roles`, {
      query: {
        include_system: options.includeSystem ?? true,
        include_archived: options.includeArchived ?? false,
        ...(options.q ? { q: options.q } : {}),
      },
    })
  },
  getRole(roleId: string): Promise<Role> {
    return apiClient.get<Role>(`${base}/custom-roles/${encodeURIComponent(roleId)}`)
  },
  createRole(payload: {
    name: string
    description: string
    scope: 'organization' | 'workspace'
    permission_keys: string[]
  }): Promise<Role> {
    return apiClient.post<Role>(`${base}/custom-roles`, payload)
  },
  updateRole(
    roleId: string,
    expectedVersion: number,
    changes: { name?: string; description?: string; permission_keys?: string[] },
  ): Promise<Role> {
    return apiClient.patch<Role>(`${base}/custom-roles/${encodeURIComponent(roleId)}`, {
      expected_version: expectedVersion,
      ...changes,
    })
  },
  cloneRole(roleId: string, name: string): Promise<Role> {
    return apiClient.post<Role>(`${base}/custom-roles/${encodeURIComponent(roleId)}/clone`, { name })
  },
  archiveRole(roleId: string, expectedVersion: number, archived: boolean): Promise<Role> {
    return apiClient.post<Role>(`${base}/custom-roles/${encodeURIComponent(roleId)}/archive`, {
      expected_version: expectedVersion,
      archived,
    })
  },
  deleteRole(roleId: string, expectedVersion: number): Promise<void> {
    return apiClient.delete<void>(
      `${base}/custom-roles/${encodeURIComponent(roleId)}?expected_version=${expectedVersion}`,
    )
  },
  listRoleAssignments(roleId: string): Promise<RoleAssignment[]> {
    return apiClient.get<RoleAssignment[]>(`${base}/custom-roles/${encodeURIComponent(roleId)}/assignments`)
  },
  assignRole(roleId: string, subjectType: 'user' | 'group', subjectId: string): Promise<RoleAssignment> {
    return apiClient.post<RoleAssignment>(`${base}/custom-roles/${encodeURIComponent(roleId)}/assignments`, {
      subject_type: subjectType,
      subject_id: subjectId,
    })
  },
  bulkAssignRole(roleId: string, userIds: string[], groupIds: string[]): Promise<BulkResultItem[]> {
    return apiClient.post<BulkResultItem[]>(`${base}/custom-roles/${encodeURIComponent(roleId)}/assignments/bulk`, {
      user_ids: userIds,
      group_ids: groupIds,
    })
  },
  unassignRole(roleId: string, assignmentId: string, subjectType: 'user' | 'group'): Promise<void> {
    return apiClient.delete<void>(
      `${base}/custom-roles/${encodeURIComponent(roleId)}/assignments/${encodeURIComponent(assignmentId)}?subject_type=${subjectType}`,
    )
  },
}
