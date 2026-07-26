import { apiClient } from '@/shared/lib/apiClient'

export type AuditResult = 'success' | 'denied' | 'failed' | 'error'

export interface AuditEvent {
  id: string
  actor: string
  action: string
  resource: string
  workspace: string
  org: string
  ip: string
  result: AuditResult
  ts: string
  correlationId: string
  before?: Record<string, unknown>
  after?: Record<string, unknown>
}

interface AuditEventDto {
  id: string
  occurred_at: string
  actor_user_id: string | null
  organization_id: string | null
  workspace_id: string | null
  correlation_id: string
  event_type: string
  action: string
  outcome: string
  reason_code: string | null
  resource_type: string | null
  resource_id: string | null
  metadata: Record<string, unknown>
}

interface AuditEventPageDto {
  items: AuditEventDto[]
  limit: number
  offset: number
}

function result(value: string): AuditResult {
  if (value === 'success' || value === 'denied' || value === 'failed') return value
  return 'error'
}

function resource(value: AuditEventDto): string {
  if (!value.resource_type) return value.resource_id ?? 'Not specified'
  return value.resource_id ? `${value.resource_type}:${value.resource_id}` : value.resource_type
}

function mapAuditEvent(value: AuditEventDto): AuditEvent {
  const safeDetails: Record<string, unknown> = { ...value.metadata }
  if (value.reason_code) safeDetails.reason_code = value.reason_code
  return {
    id: value.id,
    actor: value.actor_user_id ?? 'System',
    action: value.action || value.event_type,
    resource: resource(value),
    workspace: value.workspace_id ?? 'Organization-wide',
    org: value.organization_id ?? 'Platform',
    ip: 'Not stored',
    result: result(value.outcome),
    ts: value.occurred_at,
    correlationId: value.correlation_id,
    after: Object.keys(safeDetails).length ? safeDetails : undefined,
  }
}

export const auditService = {
  async list(): Promise<AuditEvent[]> {
    const response = await apiClient.get<AuditEventPageDto>('/api/v1/audit-events', {
      query: { limit: 200, offset: 0 },
      retry: 0,
    })
    return response.items.map(mapAuditEvent)
  },
}
