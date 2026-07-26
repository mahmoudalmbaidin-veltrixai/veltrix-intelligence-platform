import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  downloadWithMetadata: vi.fn(),
}))

vi.mock('@/shared/lib/apiClient', () => ({
  apiClient: api,
}))
vi.mock('@/shared/lib/download', () => ({ downloadBlob: vi.fn() }))

import { deliveryService, type DashboardExport, type ScheduledDelivery } from './delivery.service'

describe('dashboard delivery live service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses tenant-context API paths for export lifecycle', async () => {
    api.post.mockResolvedValue({ id: 'export-1' })
    await deliveryService.createExport('dashboard-1', 'pdf')
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/dashboards/dashboard-1/exports',
      expect.objectContaining({ format: 'pdf', filters: {} }),
    )
    const job = { id: 'export-1', row_version: 4 } as DashboardExport
    await deliveryService.cancelExport(job)
    expect(api.post).toHaveBeenLastCalledWith('/api/v1/dashboard-exports/export-1/cancel', { expected_version: 4 })
  })

  it('preserves optimistic version on schedule toggle and deletion', async () => {
    const schedule = {
      id: 'delivery-1',
      row_version: 7,
      name: 'Weekly',
      recipients: ['owner@example.com'],
      cc: [],
      bcc: [],
      subject: 'Dashboard',
      format: 'pdf',
      filters: {},
      schedule_type: 'weekly',
      schedule_expression: null,
      timezone: 'UTC',
      include_dashboard_link: true,
      enabled: true,
      max_retries: 3,
    } as ScheduledDelivery
    await deliveryService.toggle(schedule)
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/dashboard-deliveries/delivery-1',
      expect.objectContaining({ enabled: false, expected_version: 7 }),
    )
    await deliveryService.remove(schedule)
    expect(api.delete).toHaveBeenCalledWith('/api/v1/dashboard-deliveries/delivery-1', {
      query: { expected_version: 7 },
    })
  })
})
