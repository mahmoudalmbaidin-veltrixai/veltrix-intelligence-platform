import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: client }))

import { governanceService } from './apiGovernanceService'

describe('governance API service', () => {
  beforeEach(() => client.get.mockReset())

  it('loads authorization context without retries', async () => {
    client.get.mockResolvedValue({ permissions: [] })
    await expect(governanceService.authorizationContext()).resolves.toEqual({ permissions: [] })
    expect(client.get).toHaveBeenCalledWith('/api/v1/authorization/context', { retry: 0 })
  })

  it('loads roles from the protected backend catalog', async () => {
    client.get.mockResolvedValue([])
    await expect(governanceService.roles()).resolves.toEqual([])
    expect(client.get).toHaveBeenCalledWith('/api/v1/roles', { retry: 0 })
  })
})
