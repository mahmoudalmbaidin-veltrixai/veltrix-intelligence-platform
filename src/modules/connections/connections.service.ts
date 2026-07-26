/** Live B4 connection API. Credentials are accepted only by write methods and never cached. */
import { apiClient } from '@/shared/lib/apiClient'

export type ConnectionHealth = 'unknown' | 'healthy' | 'degraded' | 'unhealthy' | 'testing'
export type ConnectionStatus = 'active' | 'inactive' | 'archived'

export interface JsonSchemaProperty {
  title?: string
  type?: string
  default?: unknown
  minimum?: number
  maximum?: number
  enum?: string[]
  format?: string
}

export interface SafeJsonSchema {
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
}

export interface ConnectionType {
  key: string
  name: string
  description: string
  category: string
  configuration_schema: SafeJsonSchema
  secret_schema: SafeJsonSchema
  capabilities: string[]
  test_strategy: string
  is_enabled: boolean
  version: number
}

export interface Connection {
  id: string
  name: string
  description: string
  type: { key: string; name: string }
  status: ConnectionStatus
  health_status: ConnectionHealth
  configuration?: Record<string, unknown> | null
  credentials_configured: boolean
  secret_fields: Record<string, { configured: boolean }>
  credential_version: number
  last_tested_at: string | null
  last_test_status: string | null
  last_test_error_code: string | null
  last_test_latency_ms: number | null
  last_healthy_at: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface ConnectionListResponse {
  items: Connection[]
  page: number
  page_size: number
  total: number
}

export interface ConnectionTestResult {
  connection_id: string
  status: 'success' | 'failed'
  health_status: ConnectionHealth
  tested_at: string
  latency_ms: number
  message?: string
  error?: { code: string; message: string }
  correlation_id: string
}

export interface CreateConnectionPayload {
  name: string
  description: string
  connection_type: string
  configuration: Record<string, unknown>
  credentials: Record<string, string>
}

export interface UpdateConnectionPayload {
  name?: string
  description?: string
  configuration?: Record<string, unknown>
  status?: 'active' | 'inactive'
  version: number
}

export const connectionService = {
  types: () => apiClient.get<ConnectionType[]>('/api/v1/connections/types'),
  list: (page = 1, pageSize = 25) =>
    apiClient.get<ConnectionListResponse>('/api/v1/connections', { query: { page, page_size: pageSize } }),
  get: (id: string) => apiClient.get<Connection>(`/api/v1/connections/${id}`),
  create: (payload: CreateConnectionPayload) => apiClient.post<Connection>('/api/v1/connections', payload),
  update: (id: string, payload: UpdateConnectionPayload) =>
    apiClient.patch<Connection>(`/api/v1/connections/${id}`, payload),
  archive: (id: string) => apiClient.post<void>(`/api/v1/connections/${id}/archive`),
  test: (id: string) => apiClient.post<ConnectionTestResult>(`/api/v1/connections/${id}/test`),
  replaceCredentials: (id: string, credentials: Record<string, string>, expectedVersion: number) =>
    apiClient.put<{ connection_id: string; credential_version: number }>(`/api/v1/connections/${id}/credentials`, {
      credentials,
      expected_version: expectedVersion,
    }),
}

export const connectionIcon = (key: string): string => (key === 'rest_api' ? 'webhook' : 'database')
