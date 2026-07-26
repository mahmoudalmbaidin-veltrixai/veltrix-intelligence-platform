import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() }))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))

import { connectionService } from './connections.service'

describe('live connection service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses live list, type, create, update, archive, and test APIs', async () => {
    api.get.mockResolvedValue({ items: [] })
    api.post.mockResolvedValue({ id: 'connection-id' })
    await connectionService.types()
    await connectionService.list()
    await connectionService.create({
      name: 'Analytics',
      description: '',
      connection_type: 'postgresql',
      configuration: { host: 'db.example.com' },
      credentials: { password: 'write-only' },
    })
    await connectionService.update('connection-id', { name: 'Updated', version: 1 })
    await connectionService.test('connection-id')
    await connectionService.archive('connection-id')
    expect(api.get).toHaveBeenCalledWith('/api/v1/connections/types')
    expect(api.get).toHaveBeenCalledWith('/api/v1/connections', {
      query: { page: 1, page_size: 25 },
    })
    expect(api.post).toHaveBeenCalledWith('/api/v1/connections/connection-id/test')
    expect(api.patch).toHaveBeenCalledWith('/api/v1/connections/connection-id', { name: 'Updated', version: 1 })
    expect(api.post).toHaveBeenCalledWith('/api/v1/connections/connection-id/archive')
  })

  it('sends replacement credentials only to the write-only endpoint', async () => {
    api.put.mockResolvedValue({ connection_id: 'connection-id', credential_version: 2 })
    await connectionService.replaceCredentials('connection-id', { password: 'new-secret' }, 4)
    expect(api.put).toHaveBeenCalledWith('/api/v1/connections/connection-id/credentials', {
      credentials: { password: 'new-secret' },
      expected_version: 4,
    })
  })
})
