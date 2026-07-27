/** Platform super-admin (cross-tenant) API. Operator-only; backend enforces access. */
import { apiClient } from '@/shared/lib/apiClient'

const API = '/api/v1/platform'

export interface PlatformOverview {
  organizations_total: number
  organizations_active: number
  organizations_suspended: number
  workspaces_total: number
  users_total: number
  users_active: number
  users_suspended: number
  platform_admins: number
}

export interface PlatformOrganizationRow {
  id: string
  name: string
  slug: string
  status: string
  member_count: number
  workspace_count: number
  created_at: string
}

export interface PlatformOrganizationList {
  items: PlatformOrganizationRow[]
  page: number
  page_size: number
  total: number
}

export interface PlatformMemberRow {
  user_id: string
  email: string
  display_name: string
  role: string
  status: string
}

export interface PlatformWorkspaceRow {
  id: string
  name: string
  slug: string
  status: string
  is_default: boolean
}

export interface PlatformOrganizationDetail {
  id: string
  name: string
  slug: string
  status: string
  created_at: string
  members: PlatformMemberRow[]
  workspaces: PlatformWorkspaceRow[]
}

export interface PlatformUserRow {
  id: string
  email: string
  display_name: string
  status: string
  is_platform_admin: boolean
  organization_count: number
  created_at: string
  last_login_at: string | null
}

export interface PlatformUserList {
  items: PlatformUserRow[]
  page: number
  page_size: number
  total: number
}

export interface CreateOrganizationInput {
  name: string
  slug: string
  owner_email?: string | null
}

export interface CreatePlatformUserInput {
  email: string
  display_name: string
  password: string
  is_platform_admin?: boolean
  /** Optionally assign into an org + role at creation (also grants default workspace). */
  organization_id?: string | null
  organization_role?: string | null
}

export interface AddOrgMemberInput {
  email: string
  organization_role: string
}

export const platformService = {
  overview: () => apiClient.get<PlatformOverview>(`${API}/overview`),
  organizations: (page = 1, pageSize = 25, search?: string) =>
    apiClient.get<PlatformOrganizationList>(`${API}/organizations`, {
      query: { page, page_size: pageSize, ...(search ? { search } : {}) },
    }),
  organization: (id: string) => apiClient.get<PlatformOrganizationDetail>(`${API}/organizations/${id}`),
  createOrganization: (input: CreateOrganizationInput) =>
    apiClient.post<PlatformOrganizationDetail>(`${API}/organizations`, input),
  suspendOrganization: (id: string) => apiClient.post<PlatformOrganizationDetail>(`${API}/organizations/${id}/suspend`),
  activateOrganization: (id: string) =>
    apiClient.post<PlatformOrganizationDetail>(`${API}/organizations/${id}/activate`),
  users: (page = 1, pageSize = 25, search?: string) =>
    apiClient.get<PlatformUserList>(`${API}/users`, {
      query: { page, page_size: pageSize, ...(search ? { search } : {}) },
    }),
  suspendUser: (id: string) => apiClient.post<PlatformUserRow>(`${API}/users/${id}/suspend`),
  activateUser: (id: string) => apiClient.post<PlatformUserRow>(`${API}/users/${id}/activate`),
  // Admin-provisioned account (operator sets the initial password). 'display_name'
  // is the username; the login identifier is the email. Additive endpoint.
  createUser: (input: CreatePlatformUserInput) => apiClient.post<PlatformUserRow>(`${API}/users`, input),
  // Add an existing user (by email) to an organization with a role.
  addOrgMember: (organizationId: string, input: AddOrgMemberInput) =>
    apiClient.post<PlatformUserRow>(`${API}/organizations/${organizationId}/members`, input),
}
