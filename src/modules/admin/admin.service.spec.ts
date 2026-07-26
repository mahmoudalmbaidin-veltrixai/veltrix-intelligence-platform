import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
const tenancy = vi.hoisted(() => ({
  listOrganizations: vi.fn(),
  listWorkspaces: vi.fn(),
  updateOrganization: vi.fn(),
  createWorkspace: vi.fn(),
  updateWorkspace: vi.fn(),
}))
const governance = vi.hoisted(() => ({ roles: vi.fn() }))
const platform = vi.hoisted(() => ({ organization: { id: 'org-id' }, workspace: { id: 'workspace-id' } }))

vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))
vi.mock('@/shared/services/tenancy/apiTenancyService', () => ({ tenancyService: tenancy }))
vi.mock('@/shared/services/governance/apiGovernanceService', () => ({ governanceService: governance }))
vi.mock('@/shared/stores/platform', () => ({ usePlatformStore: () => platform }))

import { adminService } from './admin.service'

describe('live administration service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('creates, updates, and lists persisted workspaces in the active organization', async () => {
    const workspace = {
      id: 'new-workspace',
      organization_id: 'org-id',
      name: 'New Workspace',
      slug: 'new-workspace',
      status: 'active',
      is_default: false,
    }
    tenancy.listWorkspaces.mockResolvedValue([workspace])
    tenancy.createWorkspace.mockResolvedValue(workspace)
    tenancy.updateWorkspace.mockResolvedValue({ ...workspace, status: 'archived' })

    expect(await adminService.listWorkspaces()).toEqual([
      {
        id: 'new-workspace',
        name: 'New Workspace',
        slug: 'new-workspace',
        status: 'active',
        isDefault: false,
      },
    ])
    expect(tenancy.listWorkspaces).toHaveBeenCalledWith('org-id', true)
    await adminService.createWorkspace('New Workspace', 'new-workspace')
    await adminService.updateWorkspace('new-workspace', { status: 'archived' })

    expect(tenancy.createWorkspace).toHaveBeenCalledWith('org-id', {
      name: 'New Workspace',
      slug: 'new-workspace',
    })
    expect(tenancy.updateWorkspace).toHaveBeenCalledWith('org-id', 'new-workspace', { status: 'archived' })
  })

  it('updates the active organization through the live tenancy service', async () => {
    tenancy.updateOrganization.mockResolvedValue(undefined)
    await adminService.updateOrganization('Organization Alpha', 'organization-alpha')
    expect(tenancy.updateOrganization).toHaveBeenCalledWith('org-id', {
      name: 'Organization Alpha',
      slug: 'organization-alpha',
    })
  })

  it('creates invitations for the active organization and workspace', async () => {
    api.post.mockResolvedValue(undefined)
    await adminService.inviteMember('new.member@example.test', 'organization_member')
    expect(api.post).toHaveBeenCalledWith('/api/v1/organizations/org-id/invitations', {
      email: 'new.member@example.test',
      organization_role: 'organization_member',
      workspace_role: 'viewer',
      workspace_ids: ['workspace-id'],
    })

    api.get.mockResolvedValue({
      items: [
        {
          id: 'invitation-id',
          email: 'new.member@example.test',
          organization_role: 'organization_member',
          workspace_role: 'viewer',
          workspace_ids: ['workspace-id'],
          status: 'pending',
          expires_at: '2026-07-24T00:00:00Z',
          created_at: '2026-07-21T00:00:00Z',
        },
      ],
    })
    expect(await adminService.listInvitations()).toEqual([
      {
        id: 'invitation-id',
        email: 'new.member@example.test',
        organizationRole: 'organization_member',
        workspaceRole: 'viewer',
        workspaceIds: ['workspace-id'],
        status: 'pending',
        expiresAt: '2026-07-24T00:00:00Z',
        createdAt: '2026-07-21T00:00:00Z',
      },
    ])

    api.delete.mockResolvedValue(undefined)
    await adminService.revokeInvitation('invitation-id')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/organizations/org-id/invitations/invitation-id')
  })
})
