/**
 * Marketplace service (mock).
 *
 * INTEGRATION POINT
 *   Live backend:
 *     GET /api/v1/marketplace/extensions            -> Extension[]
 *     GET /api/v1/marketplace/extensions/:id        -> Extension
 *     POST /api/v1/marketplace/extensions/:id/install
 *   Swap `marketplaceService` for a live adapter; the contract is identical.
 */
import { latency } from '@/shared/lib/mock'

export type ExtensionCategory =
  | 'Connectors'
  | 'Pipeline Nodes'
  | 'Dashboard Widgets'
  | 'AI Tools'
  | 'Automation Actions'
  | 'Templates'

export type ExtensionStatus =
  | 'available'
  | 'installed'
  | 'beta'
  | 'internal'
  | 'coming-soon'
  | 'restricted'
  | 'incompatible'

export interface Extension {
  id: string
  name: string
  category: ExtensionCategory
  status: ExtensionStatus
  author: string
  description: string
  version: string
  installs: number
  rating: number
  featured?: boolean
  /** Minimum plan required to install. */
  requiredPlan?: string
  permissions?: string[]
  dependencies?: string[]
  compatibility?: string
}

/** Icon used to represent each extension category across the UI. */
export const CATEGORY_ICON: Record<ExtensionCategory, string> = {
  Connectors: 'plug',
  'Pipeline Nodes': 'workflow',
  'Dashboard Widgets': 'chart',
  'AI Tools': 'sparkles',
  'Automation Actions': 'bot',
  Templates: 'layers',
}

const EXTENSIONS: Extension[] = [
  { id: 'ext_databricks', name: 'Databricks Connector', category: 'Connectors', status: 'available', author: 'Veltrix', description: 'Read and write to Databricks Lakehouse with Unity Catalog governance and photon-accelerated pushdown queries.', version: '2.4.1', installs: 12840, rating: 4.8, featured: true, requiredPlan: 'business', permissions: ['connection:write', 'dataset:read'], compatibility: 'Platform v3.2+' },
  { id: 'ext_snowflake', name: 'Snowflake Sync', category: 'Connectors', status: 'installed', author: 'Veltrix', description: 'Bidirectional Snowflake ingestion with warehouse-scoped compute isolation and incremental change tracking.', version: '3.1.0', installs: 18220, rating: 4.9, featured: true, permissions: ['connection:write'], compatibility: 'Platform v3.0+' },
  { id: 'ext_kafka', name: 'Kafka Streaming Source', category: 'Connectors', status: 'beta', author: 'Community', description: 'Stream events from Apache Kafka topics into real-time pipelines with schema registry support.', version: '0.9.2', installs: 3410, rating: 4.3, permissions: ['connection:write', 'pipeline:write'], compatibility: 'Platform v3.3+' },
  { id: 'ext_workday', name: 'Workday HR', category: 'Connectors', status: 'restricted', author: 'Veltrix', description: 'HR and finance data ingestion. Requires an enterprise governance approval before activation.', version: '1.2.0', installs: 940, rating: 4.1, requiredPlan: 'enterprise', permissions: ['connection:write', 'governance:read'], compatibility: 'Platform v3.1+' },
  { id: 'ext_python_node', name: 'Python Transform Node', category: 'Pipeline Nodes', status: 'installed', author: 'Veltrix', description: 'Run arbitrary Python (pandas, numpy) inside a sandboxed pipeline node with pinned dependencies.', version: '4.0.3', installs: 22100, rating: 4.7, permissions: ['pipeline:write'], compatibility: 'Platform v3.0+' },
  { id: 'ext_dedupe', name: 'Fuzzy Dedupe', category: 'Pipeline Nodes', status: 'available', author: 'Community', description: 'Probabilistic record linkage and deduplication with configurable match thresholds.', version: '1.6.0', installs: 5620, rating: 4.4, permissions: ['pipeline:write'], compatibility: 'Platform v3.1+' },
  { id: 'ext_geocode', name: 'Geocoding Enricher', category: 'Pipeline Nodes', status: 'coming-soon', author: 'Veltrix', description: 'Enrich address columns with latitude/longitude and administrative regions. Arriving next release.', version: '0.4.0', installs: 0, rating: 0, compatibility: 'Platform v3.4+' },
  { id: 'ext_map_widget', name: 'Geo Map Widget', category: 'Dashboard Widgets', status: 'available', author: 'Veltrix', description: 'Choropleth and point maps with drill-down, clustering and custom GeoJSON layers.', version: '2.0.1', installs: 9870, rating: 4.6, permissions: ['dashboard:write'], compatibility: 'Platform v3.2+' },
  { id: 'ext_sankey', name: 'Sankey Flow Chart', category: 'Dashboard Widgets', status: 'beta', author: 'Community', description: 'Visualize flows and transitions between stages with an interactive Sankey diagram.', version: '0.8.1', installs: 2140, rating: 4.2, permissions: ['dashboard:write'], compatibility: 'Platform v3.3+' },
  { id: 'ext_cohort', name: 'Cohort Retention Grid', category: 'Dashboard Widgets', status: 'available', author: 'Veltrix', description: 'Retention heatmap widget with configurable cohort windows and color scales.', version: '1.3.0', installs: 6410, rating: 4.5, permissions: ['dashboard:write'], compatibility: 'Platform v3.1+' },
  { id: 'ext_anomaly', name: 'Anomaly Detection', category: 'AI Tools', status: 'installed', author: 'Veltrix', description: 'Automated statistical and ML anomaly detection over metrics with alerting hooks.', version: '2.2.0', installs: 8330, rating: 4.7, requiredPlan: 'business', permissions: ['ai:use', 'ai:configure'], compatibility: 'Platform v3.2+' },
  { id: 'ext_forecast', name: 'Time-Series Forecasting', category: 'AI Tools', status: 'available', author: 'Veltrix', description: 'Prophet and ARIMA forecasting models exposed as a first-class semantic measure.', version: '1.9.0', installs: 7120, rating: 4.6, requiredPlan: 'business', permissions: ['ai:use'], compatibility: 'Platform v3.2+' },
  { id: 'ext_llm_gateway', name: 'LLM Gateway (Internal)', category: 'AI Tools', status: 'internal', author: 'Veltrix Platform', description: 'Internal-only model routing and prompt governance layer. Not available for external install.', version: '5.0.0', installs: 0, rating: 0, permissions: ['ai:configure'], compatibility: 'Platform v3.3+' },
  { id: 'ext_slack', name: 'Slack Notifier', category: 'Automation Actions', status: 'installed', author: 'Veltrix', description: 'Send rich, templated messages to Slack channels from automation workflows.', version: '3.0.2', installs: 15400, rating: 4.8, permissions: ['automation:write'], compatibility: 'Platform v3.0+' },
  { id: 'ext_pagerduty', name: 'PagerDuty Incident', category: 'Automation Actions', status: 'available', author: 'Community', description: 'Open, update and resolve PagerDuty incidents when pipeline or data-quality checks fail.', version: '1.4.0', installs: 4230, rating: 4.4, permissions: ['automation:write'], compatibility: 'Platform v3.1+' },
  { id: 'ext_webhook_action', name: 'Signed Webhook', category: 'Automation Actions', status: 'incompatible', author: 'Community', description: 'HMAC-signed outbound webhooks. Requires a newer runtime than your current deployment.', version: '2.1.0', installs: 1980, rating: 4.0, permissions: ['automation:write', 'developer:write'], compatibility: 'Platform v3.5+' },
  { id: 'ext_tmpl_finance', name: 'Finance Starter Pack', category: 'Templates', status: 'available', author: 'Veltrix', description: 'Pre-built pipelines, semantic model and dashboards for financial reporting and FP&A.', version: '2.0.0', installs: 6890, rating: 4.7, compatibility: 'Platform v3.2+' },
  { id: 'ext_tmpl_saas', name: 'SaaS Metrics Template', category: 'Templates', status: 'available', author: 'Veltrix', description: 'MRR, churn, cohort and expansion dashboards wired to a canonical SaaS semantic layer.', version: '1.5.0', installs: 8120, rating: 4.8, featured: true, compatibility: 'Platform v3.1+' },
]

export interface MarketplaceQuery {
  search?: string
  category?: ExtensionCategory | 'all'
}

export const marketplaceService = {
  async list(params?: MarketplaceQuery): Promise<Extension[]> {
    await latency()
    return EXTENSIONS.filter((e) => {
      if (params?.category && params.category !== 'all' && e.category !== params.category) return false
      if (params?.search) {
        const q = params.search.toLowerCase()
        return (
          e.name.toLowerCase().includes(q) ||
          e.author.toLowerCase().includes(q) ||
          e.description.toLowerCase().includes(q)
        )
      }
      return true
    }).map((e) => ({ ...e }))
  },

  async get(id: string): Promise<Extension | undefined> {
    await latency(120, 320)
    const found = EXTENSIONS.find((e) => e.id === id)
    return found ? { ...found } : undefined
  },
}
