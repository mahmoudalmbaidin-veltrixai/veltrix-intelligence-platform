import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))
vi.mock('@/shared/config/env', () => ({ config: { apiMode: 'live' } }))

import { datasetService } from './datasets.service'

const apiDataset = {
  id: 'dataset-1',
  connection_id: 'connection-1',
  dataset_type: 'table',
  source_schema: 'public',
  source_name: 'orders',
  source_object_type: 'table',
  is_read_only: true,
  display_name: 'Orders',
  description: 'Orders',
  tags: [],
  status: 'active',
  certification_status: 'uncertified',
  qualified_name: 'warehouse.public.orders',
  row_count_estimate: 42,
  last_discovered_at: '2026-08-10T00:00:00Z',
  quality_status: 'passing',
  quality_score: 97,
  classification: 'internal',
  version: 3,
}

describe('datasetService list projection', () => {
  beforeEach(() => vi.clearAllMocks())

  it('hydrates a page and its quality score with one bounded request', async () => {
    api.get.mockResolvedValue({ items: [apiDataset], total: 250, page: 2, page_size: 20 })

    const result = await datasetService.listPage({ page: 2, pageSize: 20, search: 'orders' })

    expect(result).toMatchObject({ total: 250, page: 2, pageSize: 20 })
    expect(result.items[0]).toMatchObject({ id: 'dataset-1', name: 'Orders', qualityScore: 97 })
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith('/datasets', {
      query: { page: 2, page_size: 20, search: 'orders', status: undefined },
    })
    expect(api.get.mock.calls.some(([url]) => String(url).includes('/quality'))).toBe(false)
  })

  it('returns an empty authorized page without issuing detail requests', async () => {
    api.get.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 })

    await expect(datasetService.listPage({ pageSize: 50 })).resolves.toEqual({
      items: [],
      total: 0,
      page: 1,
      pageSize: 50,
    })
    expect(api.get).toHaveBeenCalledTimes(1)
  })
})
