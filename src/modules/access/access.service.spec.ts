import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))

import { accessService } from './access.service'

describe('live access-control service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists groups with the include_archived query flag', async () => {
    api.get.mockResolvedValue([])
    await accessService.listGroups(true)
    expect(api.get).toHaveBeenCalledWith('/api/v1/groups', { query: { include_archived: true } })
  })

  it('creates a group with name and description', async () => {
    api.post.mockResolvedValue({ id: 'g1' })
    await accessService.createGroup('Data Platform', 'Owns pipelines')
    expect(api.post).toHaveBeenCalledWith('/api/v1/groups', {
      name: 'Data Platform',
      description: 'Owns pipelines',
    })
  })

  it('sends optimistic version on update and archive', async () => {
    api.patch.mockResolvedValue({ id: 'g1' })
    api.post.mockResolvedValue({ id: 'g1' })
    await accessService.updateGroup('g1', 3, { name: 'Renamed' })
    expect(api.patch).toHaveBeenCalledWith('/api/v1/groups/g1', {
      expected_version: 3,
      name: 'Renamed',
    })
    await accessService.archiveGroup('g1', 4, true)
    expect(api.post).toHaveBeenCalledWith('/api/v1/groups/g1/archive', {
      expected_version: 4,
      archived: true,
    })
  })

  it('deletes a group with the expected_version guard in the query string', async () => {
    api.delete.mockResolvedValue(undefined)
    await accessService.deleteGroup('g1', 5)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/groups/g1?expected_version=5')
  })

  it('manages group membership', async () => {
    api.post.mockResolvedValue(undefined)
    api.delete.mockResolvedValue(undefined)
    await accessService.addMember('g1', 'u1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/groups/g1/members', { user_id: 'u1' })
    await accessService.removeMember('g1', 'u1')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/groups/g1/members/u1')
  })

  it('searches principals by query', async () => {
    api.get.mockResolvedValue([])
    await accessService.searchPrincipals('ana')
    expect(api.get).toHaveBeenCalledWith('/api/v1/principals/search', {
      query: { q: 'ana', limit: 50 },
    })
  })

  it('grants and revokes resource access', async () => {
    api.post.mockResolvedValue({ id: 'e1' })
    api.delete.mockResolvedValue(undefined)
    await accessService.grantResourceAccess('dashboard', 'd1', {
      subject_type: 'group',
      subject_id: 'g1',
      access_level: 'edit',
      effect: 'allow',
      expires_at: null,
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/resources/dashboard/d1/access', {
      subject_type: 'group',
      subject_id: 'g1',
      access_level: 'edit',
      effect: 'allow',
      expires_at: null,
    })
    await accessService.revokeResourceAccess('dashboard', 'd1', 'e1')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/resources/dashboard/d1/access/e1')
  })

  it('computes effective access and simulates a specific user', async () => {
    api.get.mockResolvedValue({ level: 'view' })
    await accessService.effectiveAccess('dashboard', 'd1', 'u2')
    expect(api.get).toHaveBeenCalledWith('/api/v1/resources/dashboard/d1/effective', {
      query: { user_id: 'u2' },
    })
    api.post.mockResolvedValue({ level: 'view' })
    await accessService.simulateAccess('dashboard', 'd1', 'u2')
    expect(api.post).toHaveBeenCalledWith('/api/v1/resources/dashboard/d1/simulate', {
      user_id: 'u2',
    })
  })

  it('searches resources for the tenant-scoped picker', async () => {
    api.get.mockResolvedValue([])
    await accessService.searchResources('pipeline', 'ingest')
    expect(api.get).toHaveBeenCalledWith('/api/v1/resources/pipeline/search', {
      query: { q: 'ingest' },
    })
  })

  it('loads the authoritative permission catalog and role list', async () => {
    api.get.mockResolvedValue([])
    await accessService.permissionCatalog()
    expect(api.get).toHaveBeenCalledWith('/api/v1/permission-catalog')
    await accessService.listRoles({ includeArchived: true, q: 'curator' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/custom-roles', {
      query: { include_system: true, include_archived: true, q: 'curator' },
    })
  })

  it('creates, clones, archives, and deletes custom roles with guards', async () => {
    api.post.mockResolvedValue({ id: 'r1' })
    await accessService.createRole({
      name: 'Curator',
      description: '',
      scope: 'organization',
      permission_keys: ['dashboard.read'],
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/custom-roles', {
      name: 'Curator',
      description: '',
      scope: 'organization',
      permission_keys: ['dashboard.read'],
    })
    await accessService.cloneRole('r1', 'Curator copy')
    expect(api.post).toHaveBeenCalledWith('/api/v1/custom-roles/r1/clone', { name: 'Curator copy' })
    await accessService.archiveRole('r1', 2, true)
    expect(api.post).toHaveBeenCalledWith('/api/v1/custom-roles/r1/archive', {
      expected_version: 2,
      archived: true,
    })
    api.delete.mockResolvedValue(undefined)
    await accessService.deleteRole('r1', 3)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/custom-roles/r1?expected_version=3')
  })

  it('assigns, bulk-assigns, and unassigns roles', async () => {
    api.post.mockResolvedValue({ id: 'a1' })
    await accessService.assignRole('r1', 'user', 'u1')
    expect(api.post).toHaveBeenCalledWith('/api/v1/custom-roles/r1/assignments', {
      subject_type: 'user',
      subject_id: 'u1',
    })
    await accessService.bulkAssignRole('r1', ['u1', 'u2'], ['g1'])
    expect(api.post).toHaveBeenCalledWith('/api/v1/custom-roles/r1/assignments/bulk', {
      user_ids: ['u1', 'u2'],
      group_ids: ['g1'],
    })
    api.delete.mockResolvedValue(undefined)
    await accessService.unassignRole('r1', 'a1', 'group')
    expect(api.delete).toHaveBeenCalledWith('/api/v1/custom-roles/r1/assignments/a1?subject_type=group')
  })
})
