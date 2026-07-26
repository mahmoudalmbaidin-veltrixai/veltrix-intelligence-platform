import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))

import { auditService } from './auditService'

describe('live governance audit service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads the B3 audit endpoint and maps only safe persisted fields', async () => {
    api.get.mockResolvedValue({
      items: [
        {
          id: 'event-id',
          occurred_at: '2026-07-21T12:00:00Z',
          actor_user_id: 'actor-id',
          organization_id: 'org-id',
          workspace_id: 'workspace-id',
          correlation_id: 'correlation-id',
          event_type: 'connection.tested',
          action: 'connection.tested',
          outcome: 'failed',
          reason_code: 'CONNECTION_TIMEOUT',
          resource_type: 'connection',
          resource_id: 'connection-id',
          metadata: { health_status: 'unhealthy' },
        },
      ],
      limit: 200,
      offset: 0,
    })

    const events = await auditService.list()

    expect(api.get).toHaveBeenCalledWith('/api/v1/audit-events', {
      query: { limit: 200, offset: 0 },
      retry: 0,
    })
    expect(events[0]).toEqual({
      id: 'event-id',
      actor: 'actor-id',
      action: 'connection.tested',
      resource: 'connection:connection-id',
      workspace: 'workspace-id',
      org: 'org-id',
      ip: 'Not stored',
      result: 'failed',
      ts: '2026-07-21T12:00:00Z',
      correlationId: 'correlation-id',
      after: { health_status: 'unhealthy', reason_code: 'CONNECTION_TIMEOUT' },
    })
  })
})
