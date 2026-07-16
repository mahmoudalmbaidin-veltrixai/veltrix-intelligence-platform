/**
 * Datasets + Data Quality service (mock).
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
  source: string
  rowCount: number
  freshness: string
  qualityScore: number
  sensitive: boolean
}

export type QualityDimension =
  | 'completeness'
  | 'validity'
  | 'uniqueness'
  | 'freshness'
  | 'consistency'
export type QualitySeverity = 'low' | 'medium' | 'high'
export type QualityRuleStatus = 'passing' | 'failing' | 'warning'

export interface QualityRule {
  id: string
  name: string
  dimension: QualityDimension
  severity: QualitySeverity
  status: QualityRuleStatus
  lastRun: string
  passRate: number
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
}

export interface CreateRulePayload {
  name: string
  dimension: QualityDimension
  severity: QualitySeverity
  threshold: number
}

const DATASETS: Dataset[] = [
  { id: 'ds_orders', name: 'fct_orders', description: 'Order-grain fact table with revenue, discounts and fulfilment status.', owner: 'Revenue Ops', workspace: 'Analytics', tags: ['finance', 'core', 'certified'], status: 'active', certified: true, source: 'Core Warehouse (Postgres)', rowCount: 1_284_502, freshness: isoAgo(35), qualityScore: 96, sensitive: false },
  { id: 'ds_customers', name: 'dim_customers', description: 'Customer dimension with segmentation and lifecycle attributes.', owner: 'Revenue Ops', workspace: 'Analytics', tags: ['core', 'pii'], status: 'active', certified: true, source: 'Core Warehouse (Postgres)', rowCount: 84_213, freshness: isoAgo(60), qualityScore: 88, sensitive: true },
  { id: 'ds_invoices', name: 'fct_invoices', description: 'Invoice line items with tax and currency normalisation.', owner: 'Finance', workspace: 'Revenue Ops', tags: ['finance'], status: 'active', certified: true, source: 'ERP (SQL Server)', rowCount: 902_144, freshness: isoAgo(180), qualityScore: 91, sensitive: false },
  { id: 'ds_products', name: 'dim_products', description: 'Product catalog with categories, SKUs and pricing tiers.', owner: 'Merchandising', workspace: 'Analytics', tags: ['core'], status: 'active', certified: false, source: 'Core Warehouse (Postgres)', rowCount: 12_408, freshness: isoAgo(240), qualityScore: 79, sensitive: false },
  { id: 'ds_web_events', name: 'stg_web_events', description: 'Raw clickstream events staged from the data lake.', owner: 'Growth', workspace: 'Analytics', tags: ['clickstream', 'raw'], status: 'building', certified: false, source: 'Data Lake (S3)', rowCount: 42_800_000, freshness: isoAgo(12), qualityScore: 64, sensitive: false },
  { id: 'ds_marketing', name: 'fct_marketing_touch', description: 'Multi-touch attribution events across campaigns.', owner: 'Growth', workspace: 'Analytics', tags: ['marketing'], status: 'active', certified: false, source: 'Marketing Events API', rowCount: 5_940_112, freshness: isoAgo(90), qualityScore: 72, sensitive: false },
  { id: 'ds_support', name: 'fct_support_tickets', description: 'Support desk tickets with SLA and CSAT metrics.', owner: 'Customer Success', workspace: 'Revenue Ops', tags: ['support'], status: 'active', certified: false, source: 'Support Desk API', rowCount: 318_902, freshness: isoAgo(420), qualityScore: 83, sensitive: false },
  { id: 'ds_revenue_daily', name: 'agg_daily_revenue', description: 'Daily revenue aggregate by region, channel and segment.', owner: 'Revenue Ops', workspace: 'Analytics', tags: ['finance', 'aggregate', 'certified'], status: 'active', certified: true, source: 'Core Warehouse (Postgres)', rowCount: 36_500, freshness: isoAgo(35), qualityScore: 98, sensitive: false },
  { id: 'ds_headcount', name: 'dim_employees', description: 'Employee dimension sourced from HR systems.', owner: 'People Ops', workspace: 'Platform', tags: ['hr', 'pii'], status: 'active', certified: false, source: 'ERP (SQL Server)', rowCount: 4_210, freshness: isoAgo(1440), qualityScore: 90, sensitive: true },
  { id: 'ds_inventory', name: 'fct_inventory_snapshots', description: 'Daily inventory position by warehouse and SKU.', owner: 'Supply Chain', workspace: 'Analytics', tags: ['ops'], status: 'active', certified: false, source: 'ERP (SQL Server)', rowCount: 2_104_880, freshness: isoAgo(300), qualityScore: 85, sensitive: false },
  { id: 'ds_legacy_sales', name: 'fct_sales_legacy', description: 'Deprecated legacy sales fact retained for reconciliation.', owner: 'Finance', workspace: 'Revenue Ops', tags: ['finance', 'legacy'], status: 'deprecated', certified: false, source: 'ERP (SQL Server)', rowCount: 4_820_331, freshness: isoAgo(20160), qualityScore: 58, sensitive: false },
  { id: 'ds_finance_uploads', name: 'stg_finance_uploads', description: 'Manually uploaded finance workbooks pending validation.', owner: 'Finance', workspace: 'Revenue Ops', tags: ['finance', 'manual'], status: 'building', certified: false, source: 'Finance Uploads (CSV)', rowCount: 18_204, freshness: isoAgo(120), qualityScore: 61, sensitive: false },
]

const RULES: QualityRule[] = [
  { id: 'qr_orders_notnull', name: 'orders.order_id not null', dimension: 'completeness', severity: 'high', status: 'passing', lastRun: isoAgo(35), passRate: 100, dataset: 'fct_orders' },
  { id: 'qr_orders_amount_valid', name: 'orders.amount >= 0', dimension: 'validity', severity: 'high', status: 'passing', lastRun: isoAgo(35), passRate: 99.8, dataset: 'fct_orders' },
  { id: 'qr_customers_email_valid', name: 'customers.email format', dimension: 'validity', severity: 'medium', status: 'warning', lastRun: isoAgo(60), passRate: 97.2, dataset: 'dim_customers' },
  { id: 'qr_customers_id_unique', name: 'customers.customer_id unique', dimension: 'uniqueness', severity: 'high', status: 'passing', lastRun: isoAgo(60), passRate: 100, dataset: 'dim_customers' },
  { id: 'qr_products_freshness', name: 'products refreshed < 24h', dimension: 'freshness', severity: 'medium', status: 'failing', lastRun: isoAgo(240), passRate: 71.4, dataset: 'dim_products' },
  { id: 'qr_web_events_schema', name: 'web_events schema consistency', dimension: 'consistency', severity: 'medium', status: 'warning', lastRun: isoAgo(12), passRate: 89.5, dataset: 'stg_web_events' },
  { id: 'qr_invoices_currency', name: 'invoices.currency in ISO set', dimension: 'validity', severity: 'low', status: 'passing', lastRun: isoAgo(180), passRate: 99.9, dataset: 'fct_invoices' },
  { id: 'qr_marketing_dedup', name: 'marketing_touch de-duplicated', dimension: 'uniqueness', severity: 'medium', status: 'failing', lastRun: isoAgo(90), passRate: 82.6, dataset: 'fct_marketing_touch' },
]

const INCIDENTS: QualityIncident[] = [
  { id: 'inc_001', rule: 'products refreshed < 24h', severity: 'medium', status: 'open', owner: 'Merchandising', openedAt: isoAgo(240), dataset: 'dim_products' },
  { id: 'inc_002', rule: 'marketing_touch de-duplicated', severity: 'medium', status: 'investigating', owner: 'Growth', openedAt: isoAgo(90), dataset: 'fct_marketing_touch' },
  { id: 'inc_003', rule: 'customers.email format', severity: 'medium', status: 'investigating', owner: 'Revenue Ops', openedAt: isoAgo(300), dataset: 'dim_customers' },
  { id: 'inc_004', rule: 'orders.amount >= 0', severity: 'high', status: 'resolved', owner: 'Revenue Ops', openedAt: isoAgo(2880), dataset: 'fct_orders' },
  { id: 'inc_005', rule: 'web_events schema consistency', severity: 'low', status: 'open', owner: 'Growth', openedAt: isoAgo(45), dataset: 'stg_web_events' },
]

let createdRules: QualityRule[] = []

export const datasetService = {
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

  async get(id: string): Promise<Dataset | undefined> {
    await latency(120, 320)
    return DATASETS.find((d) => d.id === id)
  },

  async listQualityRules(): Promise<QualityRule[]> {
    await latency()
    return [...createdRules, ...RULES]
  },

  async listIncidents(): Promise<QualityIncident[]> {
    await latency()
    return INCIDENTS
  },

  async createRule(payload: CreateRulePayload): Promise<QualityRule> {
    await latency(400, 900)
    const rule: QualityRule = {
      id: `qr_new_${Math.random().toString(36).slice(2, 8)}`,
      name: payload.name,
      dimension: payload.dimension,
      severity: payload.severity,
      status: 'passing',
      lastRun: new Date().toISOString(),
      passRate: payload.threshold,
    }
    createdRules = [rule, ...createdRules]
    return rule
  },
}
