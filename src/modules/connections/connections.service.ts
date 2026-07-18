/**
 * Connections service (mock).
 *
 * INTEGRATION POINT
 *   Live backend:
 *     GET  /api/v1/connections            -> Connection[]
 *     GET  /api/v1/connections/:id        -> Connection
 *     POST /api/v1/connections            -> Connection            (create)
 *     POST /api/v1/connections/:id/test   -> { ok, latencyMs, message }
 *     GET  /api/v1/connectors             -> Connector[]           (catalog)
 *   Swap `connectionService` for a live adapter; the contract is identical.
 *
 *   NOTE: Credentials/secrets are NEVER persisted in mock mode. The wizard
 *   collects them purely for the connectivity test and discards them after.
 */
import { latency, isoAgo } from '@/shared/lib/mock'
import type { ListParams } from '@/shared/types/api'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'

export type ConnectorKind =
  | 'postgres'
  | 'mysql'
  | 'sqlserver'
  | 'csv'
  | 'excel'
  | 'rest'
  | 's3'

export type ConnectionStatus = 'healthy' | 'degraded' | 'error' | 'configuring'

export interface Connection {
  id: string
  name: string
  connector: ConnectorKind
  status: ConnectionStatus
  owner: string
  host?: string
  lastTested: string
  createdAt: string
}

export interface ConnectionTestResult {
  ok: boolean
  latencyMs: number
  message: string
}

export interface CreateConnectionPayload {
  name: string
  connector: ConnectorKind
  host?: string
  owner: string
}

export type ConnectorCategory =
  | 'Databases'
  | 'Files'
  | 'APIs'
  | 'Cloud Storage'
  | 'Business Apps'

export type ConnectorAvailability = 'available' | 'beta' | 'coming-soon' | 'restricted'

export interface Connector {
  key: string
  label: string
  category: ConnectorCategory
  status: ConnectorAvailability
  icon: string
  description: string
}

/** Icon used to represent each connector kind across the UI. */
export const CONNECTOR_ICON: Record<ConnectorKind, string> = {
  postgres: 'database',
  mysql: 'database',
  sqlserver: 'database',
  csv: 'table',
  excel: 'table',
  rest: 'webhook',
  s3: 'folder',
}

/** Human label for each connector kind. */
export const CONNECTOR_LABEL: Record<ConnectorKind, string> = {
  postgres: 'PostgreSQL',
  mysql: 'MySQL',
  sqlserver: 'SQL Server',
  csv: 'CSV',
  excel: 'Excel',
  rest: 'REST API',
  s3: 'Amazon S3',
}

/** Full connector catalog surfaced in the connector gallery. */
export const CONNECTORS: Connector[] = [
  {
    key: 'postgres',
    label: 'PostgreSQL',
    category: 'Databases',
    status: 'available',
    icon: 'database',
    description: 'Connect to PostgreSQL 11+ for relational ingestion and live query pushdown.',
  },
  {
    key: 'mysql',
    label: 'MySQL',
    category: 'Databases',
    status: 'available',
    icon: 'database',
    description: 'Ingest from MySQL / MariaDB with incremental change tracking.',
  },
  {
    key: 'sqlserver',
    label: 'SQL Server',
    category: 'Databases',
    status: 'available',
    icon: 'database',
    description: 'Microsoft SQL Server with Windows and SQL authentication.',
  },
  {
    key: 'snowflake',
    label: 'Snowflake',
    category: 'Databases',
    status: 'beta',
    icon: 'database',
    description: 'Cloud warehouse connector with warehouse-scoped compute isolation.',
  },
  {
    key: 'csv',
    label: 'CSV',
    category: 'Files',
    status: 'available',
    icon: 'table',
    description: 'Upload delimited files with schema inference and type overrides.',
  },
  {
    key: 'excel',
    label: 'Excel',
    category: 'Files',
    status: 'available',
    icon: 'table',
    description: 'Import .xlsx workbooks, per-sheet, with header row detection.',
  },
  {
    key: 'rest',
    label: 'REST API',
    category: 'APIs',
    status: 'available',
    icon: 'webhook',
    description: 'Poll any JSON REST endpoint with auth, pagination and rate limits.',
  },
  {
    key: 'graphql',
    label: 'GraphQL',
    category: 'APIs',
    status: 'beta',
    icon: 'code',
    description: 'Query GraphQL services with typed schema introspection.',
  },
  {
    key: 's3',
    label: 'Amazon S3',
    category: 'Cloud Storage',
    status: 'available',
    icon: 'folder',
    description: 'Read Parquet, CSV and JSON objects from S3 buckets and prefixes.',
  },
  {
    key: 'gcs',
    label: 'Google Cloud Storage',
    category: 'Cloud Storage',
    status: 'coming-soon',
    icon: 'folder',
    description: 'Object storage ingestion from GCS buckets. Arriving next release.',
  },
  {
    key: 'salesforce',
    label: 'Salesforce',
    category: 'Business Apps',
    status: 'beta',
    icon: 'store',
    description: 'Sync Salesforce objects with bulk API and field-level selection.',
  },
  {
    key: 'workday',
    label: 'Workday',
    category: 'Business Apps',
    status: 'restricted',
    icon: 'building',
    description: 'HR and finance data. Requires an enterprise governance approval.',
  },
]

const SEED: Connection[] = [
  { id: 'conn_pg_core', name: 'Core Warehouse (Postgres)', connector: 'postgres', status: 'healthy', owner: 'Data Platform', host: 'wh-core.veltrix.internal:5432', lastTested: isoAgo(18), createdAt: isoAgo(60 * 24 * 210) },
  { id: 'conn_pg_replica', name: 'Analytics Replica', connector: 'postgres', status: 'healthy', owner: 'Data Platform', host: 'wh-replica.veltrix.internal:5432', lastTested: isoAgo(42), createdAt: isoAgo(60 * 24 * 150) },
  { id: 'conn_mysql_billing', name: 'Billing MySQL', connector: 'mysql', status: 'degraded', owner: 'Revenue Ops', host: 'billing-db.veltrix.internal:3306', lastTested: isoAgo(6), createdAt: isoAgo(60 * 24 * 320) },
  { id: 'conn_mssql_erp', name: 'ERP (SQL Server)', connector: 'sqlserver', status: 'healthy', owner: 'Finance', host: 'erp-sql.veltrix.internal:1433', lastTested: isoAgo(120), createdAt: isoAgo(60 * 24 * 400) },
  { id: 'conn_rest_marketing', name: 'Marketing Events API', connector: 'rest', status: 'healthy', owner: 'Growth', host: 'https://api.marketing.veltrix.com', lastTested: isoAgo(35), createdAt: isoAgo(60 * 24 * 95) },
  { id: 'conn_s3_lake', name: 'Data Lake (S3)', connector: 's3', status: 'healthy', owner: 'Data Platform', host: 's3://veltrix-datalake-prod', lastTested: isoAgo(78), createdAt: isoAgo(60 * 24 * 260) },
  { id: 'conn_csv_finance', name: 'Finance Uploads (CSV)', connector: 'csv', status: 'configuring', owner: 'Finance', lastTested: isoAgo(2), createdAt: isoAgo(60 * 24 * 3) },
  { id: 'conn_excel_planning', name: 'Planning Workbooks', connector: 'excel', status: 'healthy', owner: 'FP&A', lastTested: isoAgo(240), createdAt: isoAgo(60 * 24 * 40) },
  { id: 'conn_rest_support', name: 'Support Desk API', connector: 'rest', status: 'error', owner: 'Customer Success', host: 'https://api.support.veltrix.com', lastTested: isoAgo(15), createdAt: isoAgo(60 * 24 * 70) },
]

let created: Connection[] = []

function matchesSearch(c: Connection, search?: string): boolean {
  if (!search) return true
  const q = search.toLowerCase()
  return (
    c.name.toLowerCase().includes(q) ||
    c.owner.toLowerCase().includes(q) ||
    c.connector.toLowerCase().includes(q) ||
    (c.host?.toLowerCase().includes(q) ?? false)
  )
}

export interface ConnectionService {
  list(params?: ListParams): Promise<Connection[]>
  get(id: string): Promise<Connection | undefined>
  test(id: string): Promise<ConnectionTestResult>
  create(payload: CreateConnectionPayload): Promise<Connection>
}

const mockConnectionService: ConnectionService = {
  async list(params?: ListParams): Promise<Connection[]> {
    await latency()
    const all = [...created, ...SEED]
    return all.filter((c) => matchesSearch(c, params?.search))
  },

  async get(id: string): Promise<Connection | undefined> {
    await latency(120, 320)
    return [...created, ...SEED].find((c) => c.id === id)
  },

  async test(id: string): Promise<ConnectionTestResult> {
    await latency(600, 1400)
    const conn = [...created, ...SEED].find((c) => c.id === id)
    const latencyMs = 40 + Math.round(Math.random() * 220)
    if (conn?.status === 'error') {
      return { ok: false, latencyMs, message: 'Connection refused — host unreachable (ECONNREFUSED).' }
    }
    if (conn?.status === 'degraded') {
      return { ok: true, latencyMs: latencyMs + 400, message: 'Connected, but response latency is elevated.' }
    }
    return { ok: true, latencyMs, message: 'Connection established and credentials verified.' }
  },

  async create(payload: CreateConnectionPayload): Promise<Connection> {
    await latency(500, 1000)
    const conn: Connection = {
      id: `conn_new_${Math.random().toString(36).slice(2, 8)}`,
      name: payload.name,
      connector: payload.connector,
      status: 'healthy',
      owner: payload.owner,
      host: payload.host,
      lastTested: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    }
    created = [conn, ...created]
    return conn
  },
}

const apiConnectionService: ConnectionService = {
  list: (params) => apiClient.get<Connection[]>('/connections', { query: { search: params?.search } }),
  get: (id) => apiClient.get<Connection | undefined>(`/connections/${id}`),
  test: (id) => apiClient.post<ConnectionTestResult>(`/connections/${id}/test`),
  create: (payload) => apiClient.post<Connection>('/connections', payload),
}

export const connectionService: ConnectionService = defineService(
  mockConnectionService,
  () => apiConnectionService,
)
