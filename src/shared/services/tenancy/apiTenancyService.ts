import { apiClient } from '@/shared/lib/apiClient'

export type OrganizationStatus = 'active' | 'suspended' | 'archived' | 'deleted'
export type WorkspaceStatus = 'active' | 'archived' | 'deleted'
export type MembershipRole = string

export interface AuthorizedOrganizationDto {
  id: string
  name: string
  slug: string
  status: OrganizationStatus
  membership: { role: MembershipRole; status: 'active' | 'invited' | 'suspended' | 'removed' }
}

export interface AuthorizedWorkspaceDto {
  id: string
  organization_id: string
  name: string
  slug: string
  status: WorkspaceStatus
  is_default: boolean
}

export interface CreateWorkspacePayload {
  name: string
  slug: string
}

export interface UpdateWorkspacePayload {
  name?: string
  slug?: string
  status?: WorkspaceStatus
  is_default?: boolean
}

export interface UpdateOrganizationPayload {
  name?: string
  slug?: string
  status?: OrganizationStatus
}

export interface CreateOrganizationPayload {
  name: string
  slug: string
}

export interface OrganizationCreatedDto {
  organization: AuthorizedOrganizationDto
  default_workspace: AuthorizedWorkspaceDto
}

export interface TenancyService {
  listOrganizations(): Promise<AuthorizedOrganizationDto[]>
  listWorkspaces(organizationId: string, includeArchived?: boolean): Promise<AuthorizedWorkspaceDto[]>
  createOrganization(payload: CreateOrganizationPayload): Promise<OrganizationCreatedDto>
  updateOrganization(organizationId: string, payload: UpdateOrganizationPayload): Promise<AuthorizedOrganizationDto>
  createWorkspace(organizationId: string, payload: CreateWorkspacePayload): Promise<AuthorizedWorkspaceDto>
  updateWorkspace(
    organizationId: string,
    workspaceId: string,
    payload: UpdateWorkspacePayload,
  ): Promise<AuthorizedWorkspaceDto>
  deleteWorkspace(organizationId: string, workspaceId: string): Promise<void>
}

export const tenancyService: TenancyService = {
  async listOrganizations() {
    return (await apiClient.get<{ items: AuthorizedOrganizationDto[] }>('/api/v1/organizations', { retry: 0 })).items
  },
  async listWorkspaces(organizationId, includeArchived = false) {
    return (
      await apiClient.get<{ items: AuthorizedWorkspaceDto[] }>(
        `/api/v1/organizations/${encodeURIComponent(organizationId)}/workspaces`,
        { retry: 0, query: includeArchived ? { include_archived: true } : undefined },
      )
    ).items
  },
  createOrganization(payload) {
    return apiClient.post<OrganizationCreatedDto>('/api/v1/organizations', payload)
  },
  updateOrganization(organizationId, payload) {
    return apiClient.patch<AuthorizedOrganizationDto>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}`,
      payload,
    )
  },
  createWorkspace(organizationId, payload) {
    return apiClient.post<AuthorizedWorkspaceDto>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/workspaces`,
      payload,
    )
  },
  updateWorkspace(organizationId, workspaceId, payload) {
    return apiClient.patch<AuthorizedWorkspaceDto>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/workspaces/${encodeURIComponent(workspaceId)}`,
      payload,
    )
  },
  async deleteWorkspace(organizationId, workspaceId) {
    await apiClient.delete<void>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/workspaces/${encodeURIComponent(workspaceId)}`,
    )
  },
}
