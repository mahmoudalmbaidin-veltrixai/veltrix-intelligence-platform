import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))

import { platformService } from './platform.service'

const API = '/api/v1/platform'

describe('platform admin service — user access management', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches a user access summary', async () => {
    const summary = {
      user_id: 'u1',
      username: 'e2e.member',
      display_name: 'E2E Member',
      email: null,
      status: 'active',
      default_organization_id: null,
      default_workspace_id: null,
      organizations: [],
      workspaces: [],
    }
    api.get.mockResolvedValue(summary)
    expect(await platformService.accessSummary('u1')).toEqual(summary)
    expect(api.get).toHaveBeenCalledWith(`${API}/users/u1/access-summary`)
  })

  it('assigns a user to an organization by username (email may be absent)', async () => {
    api.post.mockResolvedValue({ id: 'u1' })
    await platformService.addOrgMember('org-1', {
      username: 'e2e.member',
      organization_role: 'organization_member',
    })
    expect(api.post).toHaveBeenCalledWith(`${API}/organizations/org-1/members`, {
      username: 'e2e.member',
      organization_role: 'organization_member',
    })
  })

  it('assigns a user to a workspace by username with a workspace role', async () => {
    api.post.mockResolvedValue({ user_id: 'u1', workspaces: [] })
    await platformService.addWorkspaceMember('org-1', 'ws-1', {
      username: 'e2e.member',
      workspace_role: 'workspace_admin',
    })
    expect(api.post).toHaveBeenCalledWith(`${API}/organizations/org-1/workspaces/ws-1/members`, {
      username: 'e2e.member',
      workspace_role: 'workspace_admin',
    })
  })

  it('removing organization access targets the by-user cascade endpoint', async () => {
    api.delete.mockResolvedValue(undefined)
    await platformService.removeOrgAccess('org-1', 'u1')
    expect(api.delete).toHaveBeenCalledWith(`${API}/organizations/org-1/members/by-user/u1`)
  })

  it('removes a single workspace assignment', async () => {
    api.delete.mockResolvedValue(undefined)
    await platformService.removeWorkspaceAccess('org-1', 'ws-1', 'u1')
    expect(api.delete).toHaveBeenCalledWith(`${API}/organizations/org-1/workspaces/ws-1/members/by-user/u1`)
  })

  it('edits a user profile (email "" clears it on the backend)', async () => {
    api.patch.mockResolvedValue({ id: 'u1', email: null, display_name: 'Renamed' })
    await platformService.updateUser('u1', { display_name: 'Renamed', email: '' })
    expect(api.patch).toHaveBeenCalledWith(`${API}/users/u1`, { display_name: 'Renamed', email: '' })
  })

  it('resets a password with a required-change flag', async () => {
    api.post.mockResolvedValue({ id: 'u1' })
    await platformService.resetPassword('u1', { password: 'brand-new-secret', must_change_password: true })
    expect(api.post).toHaveBeenCalledWith(`${API}/users/u1/reset-password`, {
      password: 'brand-new-secret',
      must_change_password: true,
    })
  })

  it('creates a workspace inside an organization', async () => {
    api.post.mockResolvedValue({
      id: 'ws-1',
      name: 'Marketing',
      slug: 'marketing',
      status: 'active',
      is_default: false,
    })
    await platformService.createWorkspace('org-1', { name: 'Marketing', slug: 'marketing' })
    expect(api.post).toHaveBeenCalledWith(`${API}/organizations/org-1/workspaces`, {
      name: 'Marketing',
      slug: 'marketing',
    })
  })

  it('suspends and activates a workspace', async () => {
    api.post.mockResolvedValue({ id: 'ws-1', status: 'suspended' })
    await platformService.suspendWorkspace('org-1', 'ws-1')
    expect(api.post).toHaveBeenCalledWith(`${API}/organizations/org-1/workspaces/ws-1/suspend`)
    await platformService.activateWorkspace('org-1', 'ws-1')
    expect(api.post).toHaveBeenCalledWith(`${API}/organizations/org-1/workspaces/ws-1/activate`)
  })
})
