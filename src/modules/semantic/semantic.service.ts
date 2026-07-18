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
import { MODELS } from '@/shared/services/semanticModels'
import type { Aggregation, NumberFormat, SemanticModel } from '@/shared/types/semantic'
import { latency } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'

export type MetricStatus = 'draft' | 'published'
export type MetricFormat = NumberFormat['style']

export interface Metric {
  id: string
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
  listMetrics(): Promise<Metric[]>
  listTerms(): Promise<GlossaryTerm[]>
  createMetric(input: Omit<Metric, 'id'>): Promise<Metric>
  createTerm(input: Omit<GlossaryTerm, 'id'>): Promise<GlossaryTerm>
  modelForMeasure(measureId: string): SemanticModel | undefined
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
  /** Resolve which model a measure field belongs to (used for live preview). */
  modelForMeasure(measureId: string): SemanticModel | undefined {
    return MODELS.find((m) => m.fields.some((f) => f.id === measureId))
  },
}

const apiSemanticStudioService: SemanticStudioService = {
  listModels: () => apiClient.get<SemanticModel[]>('/semantic/models'),
  getModel: (id) => apiClient.get<SemanticModel | undefined>(`/semantic/models/${id}`),
  listMetrics: () => apiClient.get<Metric[]>('/semantic/metrics'),
  listTerms: () => apiClient.get<GlossaryTerm[]>('/semantic/glossary'),
  createMetric: (input) => apiClient.post<Metric>('/semantic/metrics', input),
  createTerm: (input) => apiClient.post<GlossaryTerm>('/semantic/glossary', input),
  // Client-side resolution against the loaded semantic models — no round-trip.
  modelForMeasure: (measureId) => MODELS.find((m) => m.fields.some((f) => f.id === measureId)),
}

export const semanticStudioService: SemanticStudioService = defineService(
  mockSemanticStudioService,
  () => apiSemanticStudioService,
)
