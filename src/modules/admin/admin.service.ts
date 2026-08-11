/** Live B2/B3 administration APIs scoped to the active organization. */
import { apiClient } from '@/shared/lib/apiClient'
import { governanceService, type RoleDto } from '@/shared/services/governance/apiGovernanceService'
import { tenancyService, type UpdateWorkspacePayload } from '@/shared/services/tenancy/apiTenancyService'
import { usePlatformStore } from '@/shared/stores/platform'
import type { TenantStatus } from '@/shared/types/identity'

export interface OrgRow {
  id: string
  name: string
  status: TenantStatus
  plan: string
  members: number
  createdAt: string
}

export interface Member {
  id: string
  name: string
  email: string
  role: string
  status: 'active' | 'invited' | 'suspended'
  lastActive: string
}

export interface WorkspaceRow {
  id: string
  name: string
  slug: string
  status: 'active' | 'archived' | 'deleted'
  isDefault: boolean
}

export interface InvitationRow {
  id: string
  email: string
  organizationRole: string
  workspaceRole: string
  workspaceIds: string[]
  status: 'pending' | 'accepted' | 'expired' | 'revoked'
  expiresAt: string
  createdAt: string
}

interface MemberDto {
  id: string
  display_name: string
  email: string
  role: string
  status: 'active' | 'invited' | 'suspended' | 'removed'
}

function activeOrganizationId(): string {
  const organizationId = usePlatformStore().organization?.id
  if (!organizationId) throw new Error('Organization context is required.')
  return organizationId
}

function mapMember(member: MemberDto): Member {
  return {
    id: member.id,
    name: member.display_name,
    email: member.email,
    role: member.role,
    status: member.status === 'removed' ? 'suspended' : member.status,
    lastActive: '',
  }
}

export const adminService = {
  async listOrgs(): Promise<OrgRow[]> {
    const organizations = await tenancyService.listOrganizations()
    return organizations.map((organization) => ({
      id: organization.id,
      name: organization.name,
      status: organization.status,
      plan: 'Not loaded',
      members: 0,
      createdAt: '',
    }))
  },

  async updateOrganization(name: string, slug: string): Promise<void> {
    await tenancyService.updateOrganization(activeOrganizationId(), { name, slug })
  },

  async listMembers(): Promise<Member[]> {
    const response = await apiClient.get<{ items: MemberDto[] }>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId())}/members`,
    )
    return response.items.map(mapMember)
  },

  async listWorkspaces(): Promise<WorkspaceRow[]> {
    const workspaces = await tenancyService.listWorkspaces(activeOrganizationId(), true)
    return workspaces.map((workspace) => ({
      id: workspace.id,
      name: workspace.name,
      slug: workspace.slug,
      status: workspace.status,
      isDefault: workspace.is_default,
    }))
  },

  async createWorkspace(name: string, slug: string): Promise<WorkspaceRow> {
    const workspace = await tenancyService.createWorkspace(activeOrganizationId(), { name, slug })
    return {
      id: workspace.id,
      name: workspace.name,
      slug: workspace.slug,
      status: workspace.status,
      isDefault: workspace.is_default,
    }
  },

  async updateWorkspace(workspaceId: string, payload: UpdateWorkspacePayload): Promise<WorkspaceRow> {
    const workspace = await tenancyService.updateWorkspace(activeOrganizationId(), workspaceId, payload)
    return {
      id: workspace.id,
      name: workspace.name,
      slug: workspace.slug,
      status: workspace.status,
      isDefault: workspace.is_default,
    }
  },

  async setDefaultWorkspace(workspaceId: string): Promise<WorkspaceRow> {
    return this.updateWorkspace(workspaceId, { is_default: true })
  },

  async deleteWorkspace(workspaceId: string): Promise<void> {
    await tenancyService.deleteWorkspace(activeOrganizationId(), workspaceId)
  },

  async listAssignableOrganizationRoles(): Promise<RoleDto[]> {
    return (await governanceService.roles()).filter((role) => role.scope === 'organization' && role.is_assignable)
  },

  async updateMember(membershipId: string, role: string): Promise<Member> {
    const member = await apiClient.patch<MemberDto>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId())}/members/${encodeURIComponent(membershipId)}`,
      { role },
    )
    return mapMember(member)
  },

  async inviteMember(email: string, organizationRole: string): Promise<void> {
    const platform = usePlatformStore()
    await apiClient.post(`/api/v1/organizations/${encodeURIComponent(activeOrganizationId())}/invitations`, {
      email,
      organization_role: organizationRole,
      workspace_role: 'viewer',
      workspace_ids: platform.workspace?.id ? [platform.workspace.id] : [],
    })
  },

  async listInvitations(): Promise<InvitationRow[]> {
    const response = await apiClient.get<{
      items: Array<{
        id: string
        email: string
        organization_role: string
        workspace_role: string
        workspace_ids: string[]
        status: InvitationRow['status']
        expires_at: string
        created_at: string
      }>
    }>(`/api/v1/organizations/${encodeURIComponent(activeOrganizationId())}/invitations`)
    return response.items.map((invitation) => ({
      id: invitation.id,
      email: invitation.email,
      organizationRole: invitation.organization_role,
      workspaceRole: invitation.workspace_role,
      workspaceIds: invitation.workspace_ids,
      status: invitation.status,
      expiresAt: invitation.expires_at,
      createdAt: invitation.created_at,
    }))
  },

  async revokeInvitation(invitationId: string): Promise<void> {
    await apiClient.delete(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId())}/invitations/${encodeURIComponent(invitationId)}`,
    )
  },

  // Removes a member from the organization (existing backend endpoint; permission
  // organization.members.remove). Backend enforces last-owner / self protections.
  async removeMember(membershipId: string): Promise<void> {
    await apiClient.delete(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId())}/members/${encodeURIComponent(membershipId)}`,
    )
  },
}
