/**
 * Datasets + Data Quality service with explicit mock and live adapters.
 *
 * INTEGRATION POINT
 *   Live backend:
 *     GET  /api/v1/datasets                     -> Dataset[]
 *     GET  /api/v1/datasets/:id                 -> Dataset
 *     GET  /api/v1/quality/rules                -> QualityRule[]
 *     POST /api/v1/quality/rules                -> QualityRule       (create)
 *     GET  /api/v1/quality/incidents            -> QualityIncident[]
 *   Swap `datasetService` for a live adapter; the contract is identical.
 */
import { latency, isoAgo } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import {
  mapResourceAccess,
  type ResourceEffectiveAccess,
  type ResourceEffectiveAccessDto,
} from '@/shared/lib/resourceAccess'
import { defineService } from '@/shared/services/serviceFactory'

export type DatasetStatus = 'active' | 'deprecated' | 'building'

export interface Dataset {
  id: string
  name: string
  description: string
  owner: string
  workspace: string
  tags: string[]
  status: DatasetStatus
  certified: boolean
  certificationStatus?: string
  certifiedByUserId?: string | null
  certifiedAt?: string | null
  certificationNote?: string | null
  source: string
  rowCount: number
  freshness: string
  qualityScore: number | null
  sensitive: boolean
  version?: number
  connectionId?: string
  sourceType?: string
  schema?: string
  table?: string
  readOnly?: boolean
  /** Present on single-dataset reads: the caller's effective access. */
  access?: ResourceEffectiveAccess
}

export interface DatasetActivityItem {
  id: string
  occurredAt: string
  actorUserId: string | null
  eventType: string
  action: string
  outcome: string
  resourceType: string | null
  resourceId: string | null
  metadata: Record<string, unknown>
}

export interface DatasetActivityPage {
  items: DatasetActivityItem[]
  limit: number
  offset: number
  total: number
}

export type QualityDimension = 'completeness' | 'validity' | 'uniqueness' | 'freshness' | 'consistency'
export type QualitySeverity = 'low' | 'medium' | 'high'
export type QualityRuleStatus = 'passing' | 'failing' | 'warning' | 'unknown' | 'not_evaluated'

export interface QualityRule {
  id: string
  name: string
  dimension: QualityDimension
  severity: QualitySeverity
  status: QualityRuleStatus
  lastRun: string
  passRate: number | null
  datasetId?: string
  dataset?: string
}

export type IncidentStatus = 'open' | 'investigating' | 'resolved'

export interface QualityIncident {
  id: string
  rule: string
  severity: QualitySeverity
  status: IncidentStatus
  owner: string
  openedAt: string
  dataset: string
  datasetId?: string
  message?: string
  observed?: string | null
  expected?: string | null
  issueDetails?: Array<Record<string, unknown>>
}

export interface QualityEvaluation {
  id: string
  status: string
  score: number | null
  totalRules: number
  passing: number
  warning: number
  failing: number
  unknown: number
  createdAt: string
  completedAt: string | null
}

export interface CreateRulePayload {
  datasetId: string
  fieldId?: string
  name: string
  ruleType: 'not_null' | 'unique' | 'accepted_values' | 'range' | 'regex' | 'freshness' | 'row_count'
  severity: QualitySeverity
  configuration: Record<string, unknown>
}

export interface DatasetField {
  id?: string
  name: string
  type: string
  nullable: boolean
  description: string
}

export interface DatasetLineage {
  nodes: Dataset[]
  edges: Array<{ from: string; to: string }>
}

export interface DatasetPreview {
  columns: Array<{
    name: string
    displayName: string
    physicalType: string
    normalizedType: string
    nullable: boolean
    sensitive: boolean
  }>
  rows: Array<Record<string, unknown>>
  page: number
  pageSize: number
  returnedRows: number
  maskedFields: string[]
  refreshedAt: string
}

export interface DatasetProfile {
  fields: Array<{
    name: string
    nullCount: number
    distinctCount: number
    minimum: string | null
    maximum: string | null
  }>
  sampleSize: number
  refreshedAt: string
}

const DATASETS: Dataset[] = [
  {
    id: 'ds_orders',
    name: 'fct_orders',
    description: 'Order-grain fact table with revenue, discounts and fulfilment status.',
    owner: 'Revenue Ops',
    workspace: 'Analytics',
    tags: ['finance', 'core', 'certified'],
    status: 'active',
    certified: true,
    source: 'Core Warehouse (Postgres)',
    rowCount: 1_284_502,
    freshness: isoAgo(35),
    qualityScore: 96,
    sensitive: false,
  },
  {
    id: 'ds_customers',
    name: 'dim_customers',
    description: 'Customer dimension with segmentation and lifecycle attributes.',
    owner: 'Revenue Ops',
    workspace: 'Analytics',
    tags: ['core', 'pii'],
    status: 'active',
    certified: true,
    source: 'Core Warehouse (Postgres)',
    rowCount: 84_213,
    freshness: isoAgo(60),
    qualityScore: 88,
    sensitive: true,
  },
  {
    id: 'ds_invoices',
    name: 'fct_invoices',
    description: 'Invoice line items with tax and currency normalisation.',
    owner: 'Finance',
    workspace: 'Revenue Ops',
    tags: ['finance'],
    status: 'active',
    certified: true,
    source: 'ERP (SQL Server)',
    rowCount: 902_144,
    freshness: isoAgo(180),
    qualityScore: 91,
    sensitive: false,
  },
  {
    id: 'ds_products',
    name: 'dim_products',
    description: 'Product catalog with categories, SKUs and pricing tiers.',
    owner: 'Merchandising',
    workspace: 'Analytics',
    tags: ['core'],
    status: 'active',
    certified: false,
    source: 'Core Warehouse (Postgres)',
    rowCount: 12_408,
    freshness: isoAgo(240),
    qualityScore: 79,
    sensitive: false,
  },
  {
    id: 'ds_web_events',
    name: 'stg_web_events',
    description: 'Raw clickstream events staged from the data lake.',
    owner: 'Growth',
    workspace: 'Analytics',
    tags: ['clickstream', 'raw'],
    status: 'building',
    certified: false,
    source: 'Data Lake (S3)',
    rowCount: 42_800_000,
    freshness: isoAgo(12),
    qualityScore: 64,
    sensitive: false,
  },
  {
    id: 'ds_marketing',
    name: 'fct_marketing_touch',
    description: 'Multi-touch attribution events across campaigns.',
    owner: 'Growth',
    workspace: 'Analytics',
    tags: ['marketing'],
    status: 'active',
    certified: false,
    source: 'Marketing Events API',
    rowCount: 5_940_112,
    freshness: isoAgo(90),
    qualityScore: 72,
    sensitive: false,
  },
  {
    id: 'ds_support',
    name: 'fct_support_tickets',
    description: 'Support desk tickets with SLA and CSAT metrics.',
    owner: 'Customer Success',
    workspace: 'Revenue Ops',
    tags: ['support'],
    status: 'active',
    certified: false,
    source: 'Support Desk API',
    rowCount: 318_902,
    freshness: isoAgo(420),
    qualityScore: 83,
    sensitive: false,
  },
  {
    id: 'ds_revenue_daily',
    name: 'agg_daily_revenue',
    description: 'Daily revenue aggregate by region, channel and segment.',
    owner: 'Revenue Ops',
    workspace: 'Analytics',
    tags: ['finance', 'aggregate', 'certified'],
    status: 'active',
    certified: true,
    source: 'Core Warehouse (Postgres)',
    rowCount: 36_500,
    freshness: isoAgo(35),
    qualityScore: 98,
    sensitive: false,
  },
  {
    id: 'ds_headcount',
    name: 'dim_employees',
    description: 'Employee dimension sourced from HR systems.',
    owner: 'People Ops',
    workspace: 'Platform',
    tags: ['hr', 'pii'],
    status: 'active',
    certified: false,
    source: 'ERP (SQL Server)',
    rowCount: 4_210,
    freshness: isoAgo(1440),
    qualityScore: 90,
    sensitive: true,
  },
  {
    id: 'ds_inventory',
    name: 'fct_inventory_snapshots',
    description: 'Daily inventory position by warehouse and SKU.',
    owner: 'Supply Chain',
    workspace: 'Analytics',
    tags: ['ops'],
    status: 'active',
    certified: false,
    source: 'ERP (SQL Server)',
    rowCount: 2_104_880,
    freshness: isoAgo(300),
    qualityScore: 85,
    sensitive: false,
  },
  {
    id: 'ds_legacy_sales',
    name: 'fct_sales_legacy',
    description: 'Deprecated legacy sales fact retained for reconciliation.',
    owner: 'Finance',
    workspace: 'Revenue Ops',
    tags: ['finance', 'legacy'],
    status: 'deprecated',
    certified: false,
    source: 'ERP (SQL Server)',
    rowCount: 4_820_331,
    freshness: isoAgo(20160),
    qualityScore: 58,
    sensitive: false,
  },
  {
    id: 'ds_finance_uploads',
    name: 'stg_finance_uploads',
    description: 'Manually uploaded finance workbooks pending validation.',
    owner: 'Finance',
    workspace: 'Revenue Ops',
    tags: ['finance', 'manual'],
    status: 'building',
    certified: false,
    source: 'Finance Uploads (CSV)',
    rowCount: 18_204,
    freshness: isoAgo(120),
    qualityScore: 61,
    sensitive: false,
  },
]

const RULES: QualityRule[] = [
  {
    id: 'qr_orders_notnull',
    name: 'orders.order_id not null',
    dimension: 'completeness',
    severity: 'high',
    status: 'passing',
    lastRun: isoAgo(35),
    passRate: 100,
    dataset: 'fct_orders',
  },
  {
    id: 'qr_orders_amount_valid',
    name: 'orders.amount >= 0',
    dimension: 'validity',
    severity: 'high',
    status: 'passing',
    lastRun: isoAgo(35),
    passRate: 99.8,
    dataset: 'fct_orders',
  },
  {
    id: 'qr_customers_email_valid',
    name: 'customers.email format',
    dimension: 'validity',
    severity: 'medium',
    status: 'warning',
    lastRun: isoAgo(60),
    passRate: 97.2,
    dataset: 'dim_customers',
  },
  {
    id: 'qr_customers_id_unique',
    name: 'customers.customer_id unique',
    dimension: 'uniqueness',
    severity: 'high',
    status: 'passing',
    lastRun: isoAgo(60),
    passRate: 100,
    dataset: 'dim_customers',
  },
  {
    id: 'qr_products_freshness',
    name: 'products refreshed < 24h',
    dimension: 'freshness',
    severity: 'medium',
    status: 'failing',
    lastRun: isoAgo(240),
    passRate: 71.4,
    dataset: 'dim_products',
  },
  {
    id: 'qr_web_events_schema',
    name: 'web_events schema consistency',
    dimension: 'consistency',
    severity: 'medium',
    status: 'warning',
    lastRun: isoAgo(12),
    passRate: 89.5,
    dataset: 'stg_web_events',
  },
  {
    id: 'qr_invoices_currency',
    name: 'invoices.currency in ISO set',
    dimension: 'validity',
    severity: 'low',
    status: 'passing',
    lastRun: isoAgo(180),
    passRate: 99.9,
    dataset: 'fct_invoices',
  },
  {
    id: 'qr_marketing_dedup',
    name: 'marketing_touch de-duplicated',
    dimension: 'uniqueness',
    severity: 'medium',
    status: 'failing',
    lastRun: isoAgo(90),
    passRate: 82.6,
    dataset: 'fct_marketing_touch',
  },
]

const INCIDENTS: QualityIncident[] = [
  {
    id: 'inc_001',
    rule: 'products refreshed < 24h',
    severity: 'medium',
    status: 'open',
    owner: 'Merchandising',
    openedAt: isoAgo(240),
    dataset: 'dim_products',
  },
  {
    id: 'inc_002',
    rule: 'marketing_touch de-duplicated',
    severity: 'medium',
    status: 'investigating',
    owner: 'Growth',
    openedAt: isoAgo(90),
    dataset: 'fct_marketing_touch',
  },
  {
    id: 'inc_003',
    rule: 'customers.email format',
    severity: 'medium',
    status: 'investigating',
    owner: 'Revenue Ops',
    openedAt: isoAgo(300),
    dataset: 'dim_customers',
  },
  {
    id: 'inc_004',
    rule: 'orders.amount >= 0',
    severity: 'high',
    status: 'resolved',
    owner: 'Revenue Ops',
    openedAt: isoAgo(2880),
    dataset: 'fct_orders',
  },
  {
    id: 'inc_005',
    rule: 'web_events schema consistency',
    severity: 'low',
    status: 'open',
    owner: 'Growth',
    openedAt: isoAgo(45),
    dataset: 'stg_web_events',
  },
]

let createdRules: QualityRule[] = []

export interface DatasetService {
  list(search?: string): Promise<Dataset[]>
  discover(input: {
    connectionId: string
    schemas: string[]
    includeNames: string[]
  }): Promise<{ discovered: number; persisted: number; warnings: string[] }>
  ingestCsv(input: {
    connectionId: string
    schema: string
    table: string
    displayName: string
    description: string
    csvContent: string
  }): Promise<{ discovered: number; persisted: number; warnings: string[] }>
  ingestFile(input: {
    fileId: string
    connectionId: string
    schema: string
    table: string
    displayName: string
    description: string
  }): Promise<{ discovered: number; persisted: number; warnings: string[] }>
  get(id: string): Promise<Dataset | undefined>
  listFields(id: string): Promise<DatasetField[]>
  preview(id: string, page?: number, pageSize?: number): Promise<DatasetPreview>
  profile(id: string): Promise<DatasetProfile>
  getLineage(id?: string): Promise<DatasetLineage>
  listQualityRules(): Promise<QualityRule[]>
  /** Dataset-scoped rules — prefer this on detail pages to avoid workspace N+1 fan-out. */
  listQualityRulesForDataset(datasetId: string): Promise<QualityRule[]>
  listIncidents(): Promise<QualityIncident[]>
  qualityHistory(datasetId: string): Promise<QualityEvaluation[]>
  createRule(payload: CreateRulePayload): Promise<QualityRule>
  deleteQualityRule?(datasetId: string, ruleId: string): Promise<void>
  runQuality(datasetId: string): Promise<{ id: string; status: string }>
  certify?(id: string, version: number, note?: string): Promise<Dataset>
  revokeCertification?(id: string, version: number, note?: string): Promise<Dataset>
  getActivity?(id: string, opts?: { limit?: number; offset?: number }): Promise<DatasetActivityPage>
  /** Soft-archive (POST /datasets/:id/archive). No restore/unarchive endpoint exists. */
  archive(id: string): Promise<void>
  /** Elevated delete (DELETE /datasets/:id) — backend soft-archives; no restore. */
  remove(id: string): Promise<void>
}

const mockDatasetService: DatasetService = {
  async list(search?: string): Promise<Dataset[]> {
    await latency()
    if (!search) return DATASETS
    const q = search.toLowerCase()
    return DATASETS.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.description.toLowerCase().includes(q) ||
        d.owner.toLowerCase().includes(q) ||
        d.tags.some((t) => t.toLowerCase().includes(q)),
    )
  },
  async discover(): Promise<{ discovered: number; persisted: number; warnings: string[] }> {
    await latency()
    return { discovered: 0, persisted: 0, warnings: [] }
  },
  async ingestCsv(): Promise<{ discovered: number; persisted: number; warnings: string[] }> {
    await latency()
    return { discovered: 0, persisted: 0, warnings: [] }
  },
  async ingestFile(): Promise<{ discovered: number; persisted: number; warnings: string[] }> {
    await latency()
    return { discovered: 0, persisted: 0, warnings: [] }
  },

  async get(id: string): Promise<Dataset | undefined> {
    await latency(120, 320)
    return DATASETS.find((d) => d.id === id)
  },
  async listFields(): Promise<DatasetField[]> {
    await latency()
    return []
  },
  async preview(): Promise<DatasetPreview> {
    await latency()
    return {
      columns: [],
      rows: [],
      page: 1,
      pageSize: 25,
      returnedRows: 0,
      maskedFields: [],
      refreshedAt: new Date().toISOString(),
    }
  },
  async profile(): Promise<DatasetProfile> {
    await latency()
    return { fields: [], sampleSize: 0, refreshedAt: new Date().toISOString() }
  },
  async getLineage(): Promise<DatasetLineage> {
    await latency()
    return {
      nodes: DATASETS.slice(0, 3),
      edges: [
        { from: DATASETS[0].id, to: DATASETS[1].id },
        { from: DATASETS[1].id, to: DATASETS[2].id },
      ],
    }
  },

  async listQualityRules(): Promise<QualityRule[]> {
    await latency()
    return [...createdRules, ...RULES]
  },

  async listQualityRulesForDataset(datasetId: string): Promise<QualityRule[]> {
    await latency()
    return [...createdRules, ...RULES].filter((rule) => rule.datasetId === datasetId)
  },

  async listIncidents(): Promise<QualityIncident[]> {
    await latency()
    return INCIDENTS
  },
  async qualityHistory(): Promise<QualityEvaluation[]> {
    return []
  },

  async createRule(payload: CreateRulePayload): Promise<QualityRule> {
    await latency(400, 900)
    const rule: QualityRule = {
      id: `qr_new_${Math.random().toString(36).slice(2, 8)}`,
      name: payload.name,
      dimension:
        payload.ruleType === 'unique' ? 'uniqueness' : payload.ruleType === 'freshness' ? 'freshness' : 'completeness',
      severity: payload.severity,
      status: 'passing',
      lastRun: new Date().toISOString(),
      passRate: null,
    }
    createdRules = [rule, ...createdRules]
    return rule
  },
  async runQuality(): Promise<{ id: string; status: string }> {
    await latency()
    return { id: 'mock-quality-job', status: 'succeeded' }
  },
  async archive(id: string): Promise<void> {
    await latency()
    const i = DATASETS.findIndex((d) => d.id === id)
    if (i >= 0) DATASETS.splice(i, 1)
  },
  async remove(id: string): Promise<void> {
    await latency()
    const i = DATASETS.findIndex((d) => d.id === id)
    if (i >= 0) DATASETS.splice(i, 1)
  },
}

interface ApiDataset {
  id: string
  connection_id: string
  dataset_type: string
  source_schema: string
  source_name: string
  source_object_type: string
  is_read_only: boolean
  display_name: string
  description: string
  tags: string[]
  status: 'active' | 'inactive' | 'archived'
  certification_status: string
  certified_by_user_id?: string | null
  certified_at?: string | null
  certification_note?: string | null
  qualified_name: string
  row_count_estimate: number | null
  last_discovered_at: string | null
  quality_status: string
  classification: string
  version: number
  access?: ResourceEffectiveAccessDto | null
}

interface ApiDatasetList {
  items: ApiDataset[]
  total: number
}

interface ApiQualityRule {
  id: string
  dataset_id: string
  name: string
  rule_type: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  status: string
  updated_at: string
  field_id: string | null
  configuration: Record<string, unknown>
}

interface ApiQualitySummary {
  status: string
  score: number | null
}
interface ApiQualityResult {
  id: string
  quality_rule_id: string
  status: string
  evaluated_at: string
  observed_value: string | null
  expected_value: string | null
  safe_message: string | null
  issue_details: Array<Record<string, unknown>>
}
interface ApiQualityEvaluation {
  id: string
  status: string
  score: number | null
  total_rules: number
  passing: number
  warning: number
  failing: number
  unknown: number
  created_at: string
  completed_at: string | null
}

interface ApiDatasetField {
  id: string
  source_name: string
  display_name: string
  description: string
  physical_data_type: string
  is_nullable: boolean
}

interface ApiLineageGraph {
  nodes: ApiDataset[]
  edges: Array<{ source_dataset_id: string; target_dataset_id: string }>
}

interface ApiDatasetPreview {
  columns: Array<{
    name: string
    display_name: string
    physical_type: string
    normalized_type: string
    nullable: boolean
    sensitive: boolean
  }>
  rows: Array<Record<string, unknown>>
  page: number
  page_size: number
  returned_rows: number
  masked_fields: string[]
  refreshed_at: string
}

interface ApiDatasetProfile {
  fields: Array<{
    name: string
    null_count: number
    distinct_count: number
    minimum: string | null
    maximum: string | null
  }>
  sample_size: number
  refreshed_at: string
}

function mapDataset(item: ApiDataset, qualityScore: number | null = null): Dataset {
  return {
    id: item.id,
    name: item.display_name,
    description: item.description,
    owner: 'Workspace',
    workspace: 'Current workspace',
    tags: item.tags,
    status: item.status === 'archived' ? 'deprecated' : item.status === 'inactive' ? 'building' : 'active',
    certified: item.certification_status === 'certified',
    certificationStatus: item.certification_status,
    certifiedByUserId: item.certified_by_user_id ?? null,
    certifiedAt: item.certified_at ?? null,
    certificationNote: item.certification_note ?? null,
    source: item.qualified_name,
    rowCount: item.row_count_estimate ?? 0,
    freshness: item.last_discovered_at ?? new Date(0).toISOString(),
    qualityScore,
    sensitive: ['personal', 'restricted', 'confidential'].includes(item.classification),
    version: item.version,
    connectionId: item.connection_id,
    sourceType: item.dataset_type || item.source_object_type,
    schema: item.source_schema,
    table: item.source_name,
    readOnly: item.is_read_only,
    access: mapResourceAccess(item.access),
  }
}

async function liveDatasets(search?: string): Promise<Dataset[]> {
  const response = await apiClient.get<ApiDatasetList>('/datasets', { query: { search, page_size: 100 } })
  const summaries = await Promise.all(
    response.items.map((item) =>
      apiClient.get<ApiQualitySummary>(`/datasets/${item.id}/quality`).catch(() => ({
        status: 'unknown',
        score: null,
      })),
    ),
  )
  return response.items.map((item, index) => mapDataset(item, summaries[index]?.score ?? null))
}

function mapQualityRule(rule: ApiQualityRule, dataset: Pick<Dataset, 'id' | 'name'>): QualityRule {
  return {
    id: rule.id,
    name: rule.name,
    dimension:
      rule.rule_type === 'unique' ? 'uniqueness' : rule.rule_type === 'freshness' ? 'freshness' : 'completeness',
    severity:
      rule.severity === 'critical' || rule.severity === 'error'
        ? 'high'
        : rule.severity === 'warning'
          ? 'medium'
          : 'low',
    status: ['passing', 'failing', 'warning', 'unknown'].includes(rule.status)
      ? (rule.status as QualityRuleStatus)
      : 'not_evaluated',
    lastRun: rule.updated_at,
    passRate: rule.status === 'passing' ? 100 : rule.status === 'not_evaluated' ? null : 0,
    dataset: dataset.name,
    datasetId: dataset.id,
  }
}

async function liveRulesForDataset(datasetId: string): Promise<QualityRule[]> {
  const [dataset, rules] = await Promise.all([
    apiClient.get<ApiDataset>(`/datasets/${datasetId}`),
    apiClient.get<ApiQualityRule[]>(`/datasets/${datasetId}/quality-rules`),
  ])
  return rules.map((rule) => mapQualityRule(rule, { id: dataset.id, name: dataset.display_name }))
}

async function liveRules(): Promise<QualityRule[]> {
  const datasets = await liveDatasets()
  const groups = await Promise.all(
    datasets.map(async (dataset) => {
      const rules = await apiClient.get<ApiQualityRule[]>(`/datasets/${dataset.id}/quality-rules`)
      return rules.map((rule) => mapQualityRule(rule, dataset))
    }),
  )
  return groups.flat()
}

async function liveIncidents(): Promise<QualityIncident[]> {
  const datasets = await liveDatasets()
  const groups = await Promise.all(
    datasets.map(async (dataset) => {
      const [rules, results] = await Promise.all([
        apiClient.get<ApiQualityRule[]>(`/datasets/${dataset.id}/quality-rules`),
        apiClient.get<ApiQualityResult[]>(`/datasets/${dataset.id}/quality-results`),
      ])
      const rulesById = new Map(rules.map((rule) => [rule.id, rule]))
      const latest = new Map<string, ApiQualityResult>()
      for (const result of results) {
        if (!latest.has(result.quality_rule_id)) latest.set(result.quality_rule_id, result)
      }
      return [...latest.values()]
        .filter((result) => ['failing', 'warning'].includes(result.status))
        .map((result): QualityIncident => {
          const rule = rulesById.get(result.quality_rule_id)
          const severity: QualitySeverity =
            rule?.severity === 'critical' || rule?.severity === 'error'
              ? 'high'
              : rule?.severity === 'warning'
                ? 'medium'
                : 'low'
          return {
            id: result.id,
            rule: rule?.name ?? 'Quality rule',
            severity,
            status: 'open',
            owner: 'Dataset owner',
            openedAt: result.evaluated_at,
            dataset: dataset.name,
            datasetId: dataset.id,
            message: result.safe_message ?? undefined,
            observed: result.observed_value,
            expected: result.expected_value,
            issueDetails: result.issue_details,
          }
        })
    }),
  )
  return groups.flat()
}

const apiDatasetService: DatasetService = {
  list: liveDatasets,
  discover: async (input) => {
    const result = await apiClient.post<{
      discovered_count: number
      persisted_count: number
      warnings: string[]
    }>('/datasets/discover', {
      connection_id: input.connectionId,
      schemas: input.schemas,
      include_object_types: ['table', 'view', 'materialized_view'],
      include_names: input.includeNames,
      persist: true,
    })
    return {
      discovered: result.discovered_count,
      persisted: result.persisted_count,
      warnings: result.warnings,
    }
  },
  ingestCsv: async (input) => {
    const result = await apiClient.post<{
      discovered_count: number
      persisted_count: number
      warnings: string[]
    }>('/datasets/ingest-csv', {
      connection_id: input.connectionId,
      source_schema: input.schema,
      source_name: input.table,
      display_name: input.displayName || null,
      description: input.description,
      csv_content: input.csvContent,
    })
    return {
      discovered: result.discovered_count,
      persisted: result.persisted_count,
      warnings: result.warnings,
    }
  },
  ingestFile: async (input) => {
    const result = await apiClient.post<{
      discovered_count: number
      persisted_count: number
      warnings: string[]
    }>('/datasets/ingest-file', {
      file_id: input.fileId,
      connection_id: input.connectionId,
      source_schema: input.schema,
      source_name: input.table,
      display_name: input.displayName || null,
      description: input.description,
    })
    return {
      discovered: result.discovered_count,
      persisted: result.persisted_count,
      warnings: result.warnings,
    }
  },
  get: async (id) => {
    const [dataset, summary] = await Promise.all([
      apiClient.get<ApiDataset>(`/datasets/${id}`),
      apiClient.get<ApiQualitySummary>(`/datasets/${id}/quality`),
    ])
    return mapDataset(dataset, summary.score)
  },
  listFields: async (id) =>
    (await apiClient.get<ApiDatasetField[]>(`/datasets/${id}/fields`)).map((field) => ({
      id: field.id,
      name: field.display_name || field.source_name,
      type: field.physical_data_type,
      nullable: field.is_nullable,
      description: field.description,
    })),
  preview: async (id, page = 1, pageSize = 25) => {
    const result = await apiClient.get<ApiDatasetPreview>(`/datasets/${id}/preview`, {
      query: { page, page_size: pageSize },
    })
    return {
      columns: result.columns.map((column) => ({
        name: column.name,
        displayName: column.display_name,
        physicalType: column.physical_type,
        normalizedType: column.normalized_type,
        nullable: column.nullable,
        sensitive: column.sensitive,
      })),
      rows: result.rows,
      page: result.page,
      pageSize: result.page_size,
      returnedRows: result.returned_rows,
      maskedFields: result.masked_fields,
      refreshedAt: result.refreshed_at,
    }
  },
  profile: async (id) => {
    const result = await apiClient.get<ApiDatasetProfile>(`/datasets/${id}/profile`)
    return {
      fields: result.fields.map((field) => ({
        name: field.name,
        nullCount: field.null_count,
        distinctCount: field.distinct_count,
        minimum: field.minimum,
        maximum: field.maximum,
      })),
      sampleSize: result.sample_size,
      refreshedAt: result.refreshed_at,
    }
  },
  getLineage: async (id) => {
    let target = id
    if (!target) {
      // Workspace-wide callers without an id still need a seed dataset; avoid
      // this path on Dataset detail (always passes id).
      const datasets = await liveDatasets()
      target = datasets[0]?.id
    }
    if (!target) return { nodes: [], edges: [] }
    const graph = await apiClient.get<ApiLineageGraph>(`/datasets/${target}/lineage`)
    return {
      nodes: graph.nodes.map((item) => mapDataset(item)),
      edges: graph.edges.map((edge) => ({ from: edge.source_dataset_id, to: edge.target_dataset_id })),
    }
  },
  listQualityRules: liveRules,
  listQualityRulesForDataset: liveRulesForDataset,
  listIncidents: liveIncidents,
  qualityHistory: async (datasetId) =>
    (await apiClient.get<ApiQualityEvaluation[]>(`/datasets/${datasetId}/quality-evaluations`)).map((item) => ({
      id: item.id,
      status: item.status,
      score: item.score,
      totalRules: item.total_rules,
      passing: item.passing,
      warning: item.warning,
      failing: item.failing,
      unknown: item.unknown,
      createdAt: item.created_at,
      completedAt: item.completed_at,
    })),
  createRule: async (payload) => {
    const dataset = await apiClient.get<ApiDataset>(`/datasets/${payload.datasetId}`)
    const rule = await apiClient.post<ApiQualityRule>(`/datasets/${payload.datasetId}/quality-rules`, {
      name: payload.name,
      field_id: payload.fieldId || null,
      rule_type: payload.ruleType,
      severity: payload.severity === 'high' ? 'error' : payload.severity === 'medium' ? 'warning' : 'info',
      configuration: payload.configuration,
    })
    return {
      id: rule.id,
      name: rule.name,
      dimension:
        rule.rule_type === 'unique' ? 'uniqueness' : rule.rule_type === 'freshness' ? 'freshness' : 'completeness',
      severity: payload.severity,
      status: 'not_evaluated',
      lastRun: rule.updated_at,
      passRate: null,
      dataset: dataset.display_name,
      datasetId: payload.datasetId,
    }
  },
  runQuality: (datasetId) =>
    apiClient.post<{ id: string; status: string }>(`/datasets/${datasetId}/quality-evaluations`),
  deleteQualityRule: (datasetId, ruleId) => apiClient.delete<void>(`/datasets/${datasetId}/quality-rules/${ruleId}`),
  certify: async (id, version, note) => {
    const [dataset, summary] = await Promise.all([
      apiClient.post<ApiDataset>(`/datasets/${id}/certify`, { version, note: note ?? null }),
      apiClient.get<ApiQualitySummary>(`/datasets/${id}/quality`).catch(() => ({ status: 'unknown', score: null })),
    ])
    return mapDataset(dataset, summary.score)
  },
  revokeCertification: async (id, version, note) => {
    const [dataset, summary] = await Promise.all([
      apiClient.post<ApiDataset>(`/datasets/${id}/certification/revoke`, { version, note: note ?? null }),
      apiClient.get<ApiQualitySummary>(`/datasets/${id}/quality`).catch(() => ({ status: 'unknown', score: null })),
    ])
    return mapDataset(dataset, summary.score)
  },
  getActivity: async (id, opts = {}) => {
    const page = await apiClient.get<{
      items: Array<{
        id: string
        occurred_at: string
        actor_user_id: string | null
        event_type: string
        action: string
        outcome: string
        resource_type: string | null
        resource_id: string | null
        metadata: Record<string, unknown>
      }>
      limit: number
      offset: number
      total: number
    }>(`/datasets/${id}/activity`, {
      query: { limit: opts.limit ?? 50, offset: opts.offset ?? 0 },
    })
    return {
      items: page.items.map((item) => ({
        id: item.id,
        occurredAt: item.occurred_at,
        actorUserId: item.actor_user_id,
        eventType: item.event_type,
        action: item.action,
        outcome: item.outcome,
        resourceType: item.resource_type,
        resourceId: item.resource_id,
        metadata: item.metadata ?? {},
      })),
      limit: page.limit,
      offset: page.offset,
      total: page.total,
    }
  },
  archive: (id) => apiClient.post<void>(`/datasets/${id}/archive`),
  remove: (id) => apiClient.delete<void>(`/datasets/${id}`),
}

export const datasetService: DatasetService = defineService(mockDatasetService, () => apiDatasetService)
