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

export type ImplementationStatus = 'available' | 'beta' | 'planned' | 'requires_agent' | 'requires_driver' | 'disabled'

export interface ConnectionType {
  key: string
  name: string
  description: string
  category: string
  subcategory: string
  vendor: string
  implementation_status: ImplementationStatus
  deployment: 'cloud' | 'on_prem' | 'hybrid'
  auth_methods: string[]
  documentation_reference: string | null
  requirements: string[]
  feature_flag: string | null
  beta: boolean
  configuration_schema: SafeJsonSchema
  secret_schema: SafeJsonSchema
  capabilities: string[]
  test_strategy: string
  is_enabled: boolean
  version: number
}

export interface StatusPresentation {
  label: string
  tone: 'success' | 'info' | 'neutral' | 'warning'
}

export const CONNECTOR_STATUS: Record<ImplementationStatus, StatusPresentation> = {
  available: { label: 'Available', tone: 'success' },
  beta: { label: 'Beta', tone: 'info' },
  planned: { label: 'Planned', tone: 'neutral' },
  requires_driver: { label: 'Requires driver', tone: 'warning' },
  requires_agent: { label: 'Requires agent', tone: 'warning' },
  disabled: { label: 'Disabled', tone: 'neutral' },
}

export const CONNECTOR_CATEGORY_LABEL: Record<string, string> = {
  database: 'Databases',
  warehouse: 'Warehouses & analytics',
  object_storage: 'Data lakes & storage',
  file: 'Files & transfer',
  api: 'APIs & integration',
  erp: 'ERP systems',
  crm: 'CRM & customer',
  marketing: 'Marketing & commerce',
  streaming: 'Streaming & messaging',
  bi: 'BI & analytics',
  collaboration: 'Collaboration & apps',
  hr_finance: 'HR, finance & identity',
  observability: 'Observability',
  email: 'Email',
}

export const DEPLOYMENT_LABEL: Record<string, string> = {
  cloud: 'Cloud',
  on_prem: 'On-premise',
  hybrid: 'Cloud / on-premise',
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
  // Backend implements DELETE as a soft-archive (elevated permission + delete
  // audit event). There is no restore/unarchive endpoint.
  remove: (id: string) => apiClient.delete<void>(`/api/v1/connections/${id}`),
  test: (id: string) => apiClient.post<ConnectionTestResult>(`/api/v1/connections/${id}/test`),
  replaceCredentials: (id: string, credentials: Record<string, string>, expectedVersion: number) =>
    apiClient.put<{ connection_id: string; credential_version: number }>(`/api/v1/connections/${id}/credentials`, {
      credentials,
      expected_version: expectedVersion,
    }),
}

const CATEGORY_ICON: Record<string, string> = {
  database: 'database',
  warehouse: 'layers',
  object_storage: 'archive',
  file: 'file',
  api: 'webhook',
  erp: 'building',
  crm: 'users',
  marketing: 'chart',
  streaming: 'activity',
  bi: 'chart',
  collaboration: 'message',
  hr_finance: 'briefcase',
  observability: 'pulse',
  email: 'mail',
}

export const connectionIcon = (keyOrCategory: string, category?: string): string => {
  if (keyOrCategory === 'rest_api') return 'webhook'
  return CATEGORY_ICON[category ?? keyOrCategory] ?? 'database'
}
