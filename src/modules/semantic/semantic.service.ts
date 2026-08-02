/**
 * Semantic Studio service (mock).
 *
 * Reuses the platform semantic layer (`MODELS` + `semanticService`) as the
 * source of truth for models/fields, and layers Studio-specific concepts on
 * top: curated Metrics (KPIs) and a Business Glossary.
 *
 * INTEGRATION POINT
 *   GET  /api/v1/semantic/models                 -> SemanticModel[]
 *   GET  /api/v1/semantic/models/:id             -> SemanticModel
 *   GET  /api/v1/semantic/metrics                -> Metric[]
 *   POST /api/v1/semantic/metrics                -> Metric (create)
 *   GET  /api/v1/semantic/glossary               -> GlossaryTerm[]
 *   POST /api/v1/semantic/glossary               -> GlossaryTerm (create)
 * Swap the mock bodies for a live adapter; the return contracts are identical.
 */
import { MODELS, semanticService } from '@/shared/services/semanticModels'
import type { Aggregation, NumberFormat, SemanticModel } from '@/shared/types/semantic'
import { latency } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import type { ResourceEffectiveAccessDto } from '@/shared/lib/resourceAccess'
import { defineService } from '@/shared/services/serviceFactory'

export type MetricStatus = 'draft' | 'published'
export type MetricFormat = NumberFormat['style']

export interface Metric {
  id: string
  modelId?: string
  name: string
  description: string
  /** References a measure field id inside one of the semantic MODELS. */
  measureId: string
  aggregation: Aggregation
  format: MetricFormat
  target?: number
  thresholds?: { warning: number; critical: number }
  owner: string
  status: MetricStatus
}

export type GlossaryStatus = 'draft' | 'approved' | 'deprecated'

export interface GlossaryTerm {
  id: string
  term: string
  definition: string
  owner: string
  steward: string
  status: GlossaryStatus
  synonyms: string[]
  relatedTerms: string[]
  linkedDatasets: string[]
}

const METRICS: Metric[] = [
  {
    id: 'mt_net_revenue',
    name: 'Net Revenue',
    description: 'Total recognised revenue across all channels, net of refunds.',
    measureId: 'revenue',
    aggregation: 'sum',
    format: 'currency',
    target: 5_200_000,
    thresholds: { warning: 4_600_000, critical: 4_100_000 },
    owner: 'Revenue Ops',
    status: 'published',
  },
  {
    id: 'mt_gross_profit',
    name: 'Gross Profit',
    description: 'Revenue less cost of goods sold across the portfolio.',
    measureId: 'profit',
    aggregation: 'sum',
    format: 'currency',
    target: 1_400_000,
    thresholds: { warning: 1_200_000, critical: 1_050_000 },
    owner: 'Finance',
    status: 'published',
  },
  {
    id: 'mt_gross_margin',
    name: 'Gross Margin',
    description: 'Profit as a percentage of revenue.',
    measureId: 'margin',
    aggregation: 'avg',
    format: 'percent',
    target: 0.3,
    thresholds: { warning: 0.24, critical: 0.2 },
    owner: 'Finance',
    status: 'published',
  },
  {
    id: 'mt_order_volume',
    name: 'Order Volume',
    description: 'Count of completed orders in the period.',
    measureId: 'orders',
    aggregation: 'sum',
    format: 'plain',
    target: 3600,
    thresholds: { warning: 3000, critical: 2600 },
    owner: 'Revenue Ops',
    status: 'published',
  },
  {
    id: 'mt_aov',
    name: 'Average Order Value',
    description: 'Mean revenue per completed order.',
    measureId: 'aov',
    aggregation: 'avg',
    format: 'currency',
    target: 160,
    thresholds: { warning: 135, critical: 120 },
    owner: 'Growth',
    status: 'draft',
  },
  {
    id: 'mt_units_sold',
    name: 'Units Sold',
    description: 'Total product units shipped across categories.',
    measureId: 'units',
    aggregation: 'sum',
    format: 'compact',
    owner: 'Supply Chain',
    status: 'draft',
  },
  {
    id: 'mt_platform_uptime',
    name: 'Platform Uptime',
    description: 'Weighted availability across production services.',
    measureId: 'uptime',
    aggregation: 'avg',
    format: 'percent',
    target: 0.999,
    thresholds: { warning: 0.995, critical: 0.99 },
    owner: 'Platform',
    status: 'published',
  },
  {
    id: 'mt_error_rate',
    name: 'Error Rate',
    description: 'Share of requests returning a server error.',
    measureId: 'error_rate',
    aggregation: 'avg',
    format: 'percent',
    target: 0.005,
    thresholds: { warning: 0.01, critical: 0.02 },
    owner: 'Platform',
    status: 'published',
  },
]

const TERMS: GlossaryTerm[] = [
  {
    id: 'gt_arr',
    term: 'Annual Recurring Revenue',
    definition: 'Normalised value of contracted subscription revenue over a 12-month period, excluding one-off fees.',
    owner: 'Finance',
    steward: 'A. Rahman',
    status: 'approved',
    synonyms: ['ARR', 'Recurring Revenue'],
    relatedTerms: ['Net Revenue', 'Churn Rate'],
    linkedDatasets: ['fct_orders', 'dim_contracts'],
  },
  {
    id: 'gt_churn',
    term: 'Churn Rate',
    definition: 'Percentage of customers who cancelled or did not renew within the reporting window.',
    owner: 'Revenue Ops',
    steward: 'L. Haddad',
    status: 'approved',
    synonyms: ['Attrition', 'Logo Churn'],
    relatedTerms: ['Annual Recurring Revenue', 'Retention'],
    linkedDatasets: ['fct_subscriptions'],
  },
  {
    id: 'gt_cac',
    term: 'Customer Acquisition Cost',
    definition: 'Fully-loaded sales and marketing spend divided by the number of new customers acquired.',
    owner: 'Growth',
    steward: 'M. Farsi',
    status: 'approved',
    synonyms: ['CAC'],
    relatedTerms: ['LTV', 'Payback Period'],
    linkedDatasets: ['fct_marketing_spend'],
  },
  {
    id: 'gt_ltv',
    term: 'Lifetime Value',
    definition: 'Projected net margin a customer contributes across the full lifetime of the relationship.',
    owner: 'Growth',
    steward: 'M. Farsi',
    status: 'draft',
    synonyms: ['LTV', 'CLV'],
    relatedTerms: ['Customer Acquisition Cost', 'Gross Margin'],
    linkedDatasets: ['fct_orders'],
  },
  {
    id: 'gt_gross_margin',
    term: 'Gross Margin',
    definition: 'Revenue remaining after cost of goods sold, expressed as a percentage of revenue.',
    owner: 'Finance',
    steward: 'A. Rahman',
    status: 'approved',
    synonyms: ['Margin %'],
    relatedTerms: ['Gross Profit', 'Net Revenue'],
    linkedDatasets: ['fct_orders', 'dim_products'],
  },
  {
    id: 'gt_active_customer',
    term: 'Active Customer',
    definition: 'A customer account with at least one billable transaction in the trailing 90 days.',
    owner: 'Revenue Ops',
    steward: 'L. Haddad',
    status: 'approved',
    synonyms: ['Active Account'],
    relatedTerms: ['Churn Rate'],
    linkedDatasets: ['dim_customers'],
  },
  {
    id: 'gt_bookings',
    term: 'Bookings',
    definition: 'Total contract value of deals closed in the period, recognised at signature.',
    owner: 'Finance',
    steward: 'A. Rahman',
    status: 'draft',
    synonyms: ['Total Contract Value', 'TCV'],
    relatedTerms: ['Net Revenue'],
    linkedDatasets: ['fct_deals'],
  },
  {
    id: 'gt_uptime',
    term: 'Uptime',
    definition: 'Proportion of time a production service is available and serving requests successfully.',
    owner: 'Platform',
    steward: 'S. Nawaz',
    status: 'approved',
    synonyms: ['Availability', 'SLA'],
    relatedTerms: ['Error Rate'],
    linkedDatasets: ['fct_service_health'],
  },
  {
    id: 'gt_error_rate',
    term: 'Error Rate',
    definition: 'Share of inbound requests that return a 5xx server error over the interval.',
    owner: 'Platform',
    steward: 'S. Nawaz',
    status: 'approved',
    synonyms: ['Failure Rate'],
    relatedTerms: ['Uptime', 'Latency'],
    linkedDatasets: ['fct_service_health'],
  },
  {
    id: 'gt_dau',
    term: 'Daily Active Users',
    definition:
      'Distinct authenticated users performing at least one action within a calendar day. Deprecated in favour of weekly cohorts.',
    owner: 'Product',
    steward: 'K. Osei',
    status: 'deprecated',
    synonyms: ['DAU'],
    relatedTerms: ['Active Customer'],
    linkedDatasets: ['fct_events'],
  },
]

export interface SemanticStudioService {
  listModels(): Promise<SemanticModel[]>
  getModel(id: string): Promise<SemanticModel | undefined>
  createModel(input: CreateSemanticModelInput): Promise<{ id: string }>
  updateModel(id: string, input: UpdateSemanticModelInput): Promise<void>
  archiveModel(id: string): Promise<void>
  validateModel(id: string): Promise<SemanticValidation>
  publishModel(id: string): Promise<void>
  getDefinition(id: string): Promise<SemanticDefinition>
  listVersions(id: string): Promise<SemanticModelVersion[]>
  createDimension(id: string, input: DimensionInput): Promise<void>
  updateDimension(id: string, dimensionId: string, input: DimensionInput): Promise<void>
  deleteDimension(id: string, dimensionId: string): Promise<void>
  createMeasure(id: string, input: MeasureInput): Promise<void>
  updateMeasure(id: string, measureId: string, input: MeasureInput): Promise<void>
  deleteMeasure(id: string, measureId: string): Promise<void>
  listMetrics(): Promise<Metric[]>
  listTerms(): Promise<GlossaryTerm[]>
  createMetric(input: Omit<Metric, 'id'>): Promise<Metric>
  createTerm(input: Omit<GlossaryTerm, 'id'>): Promise<GlossaryTerm>
}

export interface CreateSemanticModelInput {
  key: string
  name: string
  description: string
  primary_dataset_id: string
  timezone: string
  currency: string
}

export interface UpdateSemanticModelInput {
  name: string
  description: string
  timezone: string
  currency: string
  version: number
}

export interface StudioModel {
  id: string
  key: string
  name: string
  description: string
  status: 'draft' | 'published' | 'archived'
  primary_dataset_id: string
  timezone: string
  currency: string
  version_number: number
  published_version: number | null
  updated_at: string
  version: number
  /** Present on single-model reads: the caller's effective access (raw DTO). */
  access?: ResourceEffectiveAccessDto | null
}

export interface StudioField {
  id: string
  source_name: string
  display_name: string
  physical_data_type: string
  normalized_data_type: string
}

export interface StudioDimension {
  id: string
  dataset_id: string
  field_id: string
  key: string
  name: string
  description: string
  dimension_type: string
  is_time_dimension: boolean
  time_granularities: string[]
  is_hidden: boolean
}

export interface DimensionInput {
  dataset_id: string
  field_id: string
  key: string
  name: string
  description: string
  dimension_type: string
  is_time_dimension: boolean
  time_granularities: string[]
  is_hidden: boolean
}

export interface StudioMeasure {
  id: string
  dataset_id: string
  field_id: string | null
  key: string
  name: string
  description: string
  aggregation: string
  is_hidden: boolean
}

export interface MeasureInput {
  dataset_id: string
  field_id: string | null
  key: string
  name: string
  description: string
  aggregation: string
  is_hidden: boolean
}

export interface StudioMetric {
  id: string
  key: string
  name: string
  description: string
  metric_type: string
  status: string
}

export interface StudioKpi {
  id: string
  key: string
  name: string
  description: string
  status: string
}

export interface SemanticDefinition {
  model: StudioModel
  fields: StudioField[]
  dimensions: StudioDimension[]
  measures: StudioMeasure[]
  metrics: StudioMetric[]
  kpis: StudioKpi[]
}

export interface SemanticValidation {
  valid: boolean
  errors: Array<{ code: string; message: string; resource?: string }>
  warnings: Array<{ code: string; message: string; resource?: string }>
}

export interface SemanticModelVersion {
  id: string
  semantic_model_id: string
  version_number: number
  definition: {
    model?: StudioModel
    dimensions?: StudioDimension[]
    measures?: StudioMeasure[]
    metrics?: StudioMetric[]
    kpis?: StudioKpi[]
  }
  published_by_user_id: string | null
  published_at: string
}

const mockSemanticStudioService: SemanticStudioService = {
  async listModels(): Promise<SemanticModel[]> {
    await latency(120, 300)
    return MODELS
  },
  async getModel(id: string): Promise<SemanticModel | undefined> {
    await latency(100, 240)
    return MODELS.find((m) => m.id === id)
  },
  async createModel(): Promise<{ id: string }> {
    await latency()
    return { id: MODELS[0].id }
  },
  async updateModel(): Promise<void> {
    await latency()
  },
  async archiveModel(): Promise<void> {
    await latency()
  },
  async validateModel(): Promise<SemanticValidation> {
    await latency()
    return { valid: true, errors: [], warnings: [] }
  },
  async publishModel(): Promise<void> {
    await latency()
  },
  async getDefinition(id: string): Promise<SemanticDefinition> {
    await latency()
    const source = MODELS.find((item) => item.id === id) ?? MODELS[0]
    return {
      model: {
        id: source.id,
        key: source.name,
        name: source.label,
        description: source.description,
        status: source.certified ? 'published' : 'draft',
        primary_dataset_id: source.entities[0]?.id ?? source.id,
        timezone: 'UTC',
        currency: 'USD',
        version_number: 1,
        published_version: source.certified ? 1 : null,
        updated_at: source.freshness,
        version: 1,
      },
      fields: [],
      dimensions: [],
      measures: [],
      metrics: [],
      kpis: [],
    }
  },
  async listVersions(): Promise<SemanticModelVersion[]> {
    await latency()
    return []
  },
  async createDimension(): Promise<void> {
    await latency()
  },
  async updateDimension(): Promise<void> {
    await latency()
  },
  async deleteDimension(): Promise<void> {
    await latency()
  },
  async createMeasure(): Promise<void> {
    await latency()
  },
  async updateMeasure(): Promise<void> {
    await latency()
  },
  async deleteMeasure(): Promise<void> {
    await latency()
  },
  async listMetrics(): Promise<Metric[]> {
    await latency(140, 320)
    return METRICS
  },
  async listTerms(): Promise<GlossaryTerm[]> {
    await latency(140, 320)
    return TERMS
  },
  /** Persist a new metric (mock — pushes into the in-memory seed). */
  async createMetric(input: Omit<Metric, 'id'>): Promise<Metric> {
    await latency(200, 420)
    const metric: Metric = { ...input, id: `mt_${Math.random().toString(36).slice(2, 9)}` }
    METRICS.unshift(metric)
    return metric
  },
  /** Persist a new glossary term (mock). */
  async createTerm(input: Omit<GlossaryTerm, 'id'>): Promise<GlossaryTerm> {
    await latency(200, 420)
    const term: GlossaryTerm = { ...input, id: `gt_${Math.random().toString(36).slice(2, 9)}` }
    TERMS.unshift(term)
    return term
  },
}

interface LiveModel {
  id: string
}
interface LiveMeasure {
  id: string
  key: string
  aggregation: string
}
interface LiveMetric {
  id: string
  name: string
  description: string
  base_measure_id: string | null
  status: string
}
interface LiveKpi {
  id: string
  metric_id: string
  target_value: number | null
  warning_threshold: number | null
  critical_threshold: number | null
}
interface LiveTerm {
  id: string
  name: string
  definition: string
  status: GlossaryStatus
  synonyms: string[]
}
interface LiveDomain {
  id: string
}

async function listLiveMetrics(): Promise<Metric[]> {
  const models = await apiClient.get<LiveModel[]>('/semantic-models')
  const groups = await Promise.all(
    models.map(async ({ id }) => {
      const [metrics, measures, kpis] = await Promise.all([
        apiClient.get<LiveMetric[]>(`/semantic-models/${id}/metrics`),
        apiClient.get<LiveMeasure[]>(`/semantic-models/${id}/measures`),
        apiClient.get<LiveKpi[]>(`/semantic-models/${id}/kpis`),
      ])
      const byId = new Map(measures.map((item) => [item.id, item]))
      const kpiByMetric = new Map(kpis.map((item) => [item.metric_id, item]))
      return metrics.map((item): Metric => {
        const kpi = kpiByMetric.get(item.id)
        return {
          id: item.id,
          modelId: id,
          name: item.name,
          description: item.description,
          measureId: item.base_measure_id ? (byId.get(item.base_measure_id)?.key ?? '') : '',
          aggregation: (item.base_measure_id ? byId.get(item.base_measure_id)?.aggregation : 'sum') as Aggregation,
          format: 'plain',
          target: kpi?.target_value ?? undefined,
          thresholds:
            kpi?.warning_threshold != null && kpi.critical_threshold != null
              ? { warning: kpi.warning_threshold, critical: kpi.critical_threshold }
              : undefined,
          owner: 'Workspace',
          status: item.status === 'draft' ? 'draft' : 'published',
        }
      })
    }),
  )
  return groups.flat()
}

async function listLiveTerms(): Promise<GlossaryTerm[]> {
  return (await apiClient.get<LiveTerm[]>('/glossary/terms')).map((item) => ({
    id: item.id,
    term: item.name,
    definition: item.definition,
    owner: 'Workspace',
    steward: 'Workspace',
    status: item.status,
    synonyms: item.synonyms,
    relatedTerms: [],
    linkedDatasets: [],
  }))
}

function keyFor(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

async function createLiveMetric(input: Omit<Metric, 'id'>): Promise<Metric> {
  const models = await apiClient.get<LiveModel[]>('/semantic-models')
  for (const model of input.modelId ? models.filter((item) => item.id === input.modelId) : models) {
    const measures = await apiClient.get<LiveMeasure[]>(`/semantic-models/${model.id}/measures`)
    const measure = measures.find((item) => item.key === input.measureId)
    if (measure) {
      const metric = await apiClient.post<LiveMetric>(`/semantic-models/${model.id}/metrics`, {
        key: keyFor(input.name),
        name: input.name,
        description: input.description,
        metric_type: 'measure',
        base_measure_id: measure.id,
      })
      if (input.target != null || input.thresholds) {
        await apiClient.post(`/semantic-models/${model.id}/kpis`, {
          metric_id: metric.id,
          key: `${keyFor(input.name)}_kpi`,
          name: input.name,
          description: input.description,
          target_value: input.target ?? null,
          warning_threshold: input.thresholds?.warning ?? null,
          critical_threshold: input.thresholds?.critical ?? null,
          comparison_operator: 'greater_than_or_equal',
          target_period: null,
        })
      }
      return (await listLiveMetrics()).find((item) => item.name === input.name)!
    }
  }
  throw new Error('The selected measure is unavailable.')
}

async function createLiveTerm(input: Omit<GlossaryTerm, 'id'>): Promise<GlossaryTerm> {
  let [domain] = await apiClient.get<LiveDomain[]>('/glossary/domains')
  domain ??= await apiClient.post<LiveDomain>('/glossary/domains', {
    key: 'business',
    name: 'Business',
    description: 'Business terminology',
  })
  const term = await apiClient.post<LiveTerm>('/glossary/terms', {
    domain_id: domain.id,
    key: keyFor(input.term),
    name: input.term,
    definition: input.definition,
    synonyms: input.synonyms,
    examples: [],
  })
  return { ...input, id: term.id, status: term.status }
}

async function getLiveDefinition(id: string): Promise<SemanticDefinition> {
  const model = await apiClient.get<StudioModel>(`/semantic-models/${id}`)
  const [fields, dimensions, measures, metrics, kpis] = await Promise.all([
    apiClient.get<StudioField[]>(`/datasets/${model.primary_dataset_id}/fields`),
    apiClient.get<StudioDimension[]>(`/semantic-models/${id}/dimensions`),
    apiClient.get<StudioMeasure[]>(`/semantic-models/${id}/measures`),
    apiClient.get<StudioMetric[]>(`/semantic-models/${id}/metrics`),
    apiClient.get<StudioKpi[]>(`/semantic-models/${id}/kpis`),
  ])
  return { model, fields, dimensions, measures, metrics, kpis }
}

const apiSemanticStudioService: SemanticStudioService = {
  listModels: () => semanticService.listModels(),
  getModel: (id) => semanticService.getModel(id),
  createModel: (input) => apiClient.post<{ id: string }>('/semantic-models', input),
  updateModel: async (id, input) => {
    await apiClient.patch(`/semantic-models/${id}`, input)
  },
  archiveModel: async (id) => {
    await apiClient.post(`/semantic-models/${id}/archive`)
  },
  validateModel: (id) => apiClient.post<SemanticValidation>(`/semantic-models/${id}/validate`),
  publishModel: async (id) => {
    await apiClient.post(`/semantic-models/${id}/publish`)
  },
  getDefinition: getLiveDefinition,
  listVersions: (id) => apiClient.get<SemanticModelVersion[]>(`/semantic-models/${id}/versions`),
  createDimension: async (id, input) => {
    await apiClient.post(`/semantic-models/${id}/dimensions`, input)
  },
  updateDimension: async (id, dimensionId, input) => {
    await apiClient.patch(`/semantic-models/${id}/dimensions/${dimensionId}`, input)
  },
  deleteDimension: async (id, dimensionId) => {
    await apiClient.delete(`/semantic-models/${id}/dimensions/${dimensionId}`)
  },
  createMeasure: async (id, input) => {
    await apiClient.post(`/semantic-models/${id}/measures`, input)
  },
  updateMeasure: async (id, measureId, input) => {
    await apiClient.patch(`/semantic-models/${id}/measures/${measureId}`, input)
  },
  deleteMeasure: async (id, measureId) => {
    await apiClient.delete(`/semantic-models/${id}/measures/${measureId}`)
  },
  listMetrics: listLiveMetrics,
  listTerms: listLiveTerms,
  createMetric: createLiveMetric,
  createTerm: createLiveTerm,
}

export const semanticStudioService: SemanticStudioService = defineService(
  mockSemanticStudioService,
  () => apiSemanticStudioService,
)
