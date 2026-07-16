/**
 * Mock semantic models + deterministic query engine.
 *
 * INTEGRATION POINT
 *   Live backend: POST /api/v1/semantic/query  (body: SemanticQuery -> QueryResult)
 *                 GET  /api/v1/semantic/models
 *   Swap `semanticService` for a live adapter; the contract is identical.
 */
import type {
  CellValue, QueryColumn, QueryResult, SemanticField, SemanticModel, SemanticQuery,
} from '@/shared/types/semantic'
import { latency, nowIso } from '@/shared/lib/mock'

function f(
  id: string, label: string, role: SemanticField['role'], dataType: SemanticField['dataType'],
  extra: Partial<SemanticField> = {},
): SemanticField {
  return { id, name: id, label, role, dataType, ...extra }
}

const salesFields: SemanticField[] = [
  f('order_date', 'Order Date', 'time', 'date', { grains: ['day', 'week', 'month', 'quarter', 'year'], folder: 'Time' }),
  f('region', 'Region', 'dimension', 'string', { folder: 'Geography', hierarchyId: 'geo', hierarchyLevel: 0 }),
  f('country', 'Country', 'dimension', 'string', { folder: 'Geography', hierarchyId: 'geo', hierarchyLevel: 1 }),
  f('city', 'City', 'dimension', 'string', { folder: 'Geography', hierarchyId: 'geo', hierarchyLevel: 2 }),
  f('category', 'Product Category', 'dimension', 'string', { folder: 'Product' }),
  f('segment', 'Customer Segment', 'dimension', 'string', { folder: 'Customer' }),
  f('channel', 'Sales Channel', 'dimension', 'string', { folder: 'Sales' }),
  f('revenue', 'Revenue', 'measure', 'currency', { defaultAggregation: 'sum', format: { style: 'currency', currency: 'USD', decimals: 0 }, folder: 'Sales' }),
  f('profit', 'Profit', 'measure', 'currency', { defaultAggregation: 'sum', format: { style: 'currency', currency: 'USD', decimals: 0 }, folder: 'Sales' }),
  f('orders', 'Orders', 'measure', 'integer', { defaultAggregation: 'sum', folder: 'Sales' }),
  f('units', 'Units Sold', 'measure', 'integer', { defaultAggregation: 'sum', folder: 'Sales' }),
  f('margin', 'Margin %', 'metric', 'percent', { defaultAggregation: 'avg', format: { style: 'percent', decimals: 1 }, folder: 'KPIs' }),
  f('aov', 'Avg Order Value', 'metric', 'currency', { defaultAggregation: 'avg', format: { style: 'currency', currency: 'USD', decimals: 0 }, folder: 'KPIs' }),
]

const opsFields: SemanticField[] = [
  f('event_date', 'Event Date', 'time', 'date', { grains: ['day', 'week', 'month'], folder: 'Time' }),
  f('service', 'Service', 'dimension', 'string', { folder: 'Platform' }),
  f('environment', 'Environment', 'dimension', 'string', { folder: 'Platform' }),
  f('requests', 'Requests', 'measure', 'integer', { defaultAggregation: 'sum', folder: 'Traffic' }),
  f('errors', 'Errors', 'measure', 'integer', { defaultAggregation: 'sum', folder: 'Reliability' }),
  f('latency_ms', 'Latency (p95)', 'measure', 'number', { defaultAggregation: 'avg', format: { style: 'plain', decimals: 0, suffix: 'ms' }, folder: 'Reliability' }),
  f('error_rate', 'Error Rate', 'metric', 'percent', { defaultAggregation: 'avg', format: { style: 'percent', decimals: 2 }, folder: 'KPIs' }),
  f('uptime', 'Uptime', 'metric', 'percent', { defaultAggregation: 'avg', format: { style: 'percent', decimals: 2 }, folder: 'KPIs' }),
]

export const MODELS: SemanticModel[] = [
  {
    id: 'sm_sales', name: 'sales', label: 'Sales Analytics',
    description: 'Unified orders, revenue and margin across channels and regions.',
    owner: 'Revenue Ops', certified: true, freshness: nowIso(),
    entities: [{ id: 'e_sales', name: 'sales', label: 'Sales', fields: salesFields }],
    fields: salesFields,
  },
  {
    id: 'sm_ops', name: 'ops', label: 'Platform Operations',
    description: 'Service traffic, reliability and latency telemetry.',
    owner: 'Platform', certified: true, freshness: nowIso(),
    entities: [{ id: 'e_ops', name: 'ops', label: 'Operations', fields: opsFields }],
    fields: opsFields,
  },
]

/* ---- deterministic value synthesis ---- */
const DIM_VALUES: Record<string, string[]> = {
  region: ['EMEA', 'Americas', 'APAC', 'MEA'],
  country: ['Saudi Arabia', 'UAE', 'United States', 'Germany', 'Japan', 'Egypt'],
  city: ['Riyadh', 'Dubai', 'New York', 'Berlin', 'Tokyo', 'Cairo'],
  category: ['Software', 'Hardware', 'Services', 'Support', 'Training'],
  segment: ['Enterprise', 'Mid-Market', 'SMB', 'Public Sector'],
  channel: ['Direct', 'Partner', 'Self-Serve', 'Marketplace'],
  service: ['api-gateway', 'query-engine', 'ingest', 'auth', 'scheduler'],
  environment: ['production', 'staging'],
}

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0) / 0xffffffff
}

function fieldById(model: SemanticModel, id: string): SemanticField | undefined {
  return model.fields.find((x) => x.id === id)
}

function measureBase(fieldId: string): number {
  switch (fieldId) {
    case 'revenue': return 480_000
    case 'profit': return 128_000
    case 'orders': return 3200
    case 'units': return 9400
    case 'margin': return 0.27
    case 'aov': return 148
    case 'requests': return 1_250_000
    case 'errors': return 4200
    case 'latency_ms': return 180
    case 'error_rate': return 0.006
    case 'uptime': return 0.9993
    default: return 1000
  }
}

function timeSeries(grain: string, n: number): string[] {
  const out: string[] = []
  const now = new Date()
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now)
    if (grain === 'year') d.setFullYear(now.getFullYear() - i)
    else if (grain === 'quarter') d.setMonth(now.getMonth() - i * 3)
    else if (grain === 'month') d.setMonth(now.getMonth() - i)
    else if (grain === 'week') d.setDate(now.getDate() - i * 7)
    else d.setDate(now.getDate() - i)
    if (grain === 'year') out.push(String(d.getFullYear()))
    else if (grain === 'quarter') out.push(`Q${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`)
    else if (grain === 'month') out.push(d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }))
    else out.push(d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))
  }
  return out
}

export function runQuerySync(query: SemanticQuery): QueryResult {
  const model = MODELS.find((m) => m.id === query.modelId) ?? MODELS[0]
  const columns: QueryColumn[] = []
  const dimFields = query.dimensions.map((d) => ({ d, field: fieldById(model, d.fieldId) })).filter((x) => x.field)
  const measFields = query.measures.map((m) => ({ m, field: fieldById(model, m.fieldId) })).filter((x) => x.field)

  dimFields.forEach(({ d, field }) => {
    columns.push({ key: d.alias ?? d.fieldId, label: field!.label, role: field!.role, dataType: field!.dataType })
  })
  measFields.forEach(({ m, field }) => {
    columns.push({ key: m.alias ?? m.fieldId, label: field!.label, role: field!.role, dataType: field!.dataType, format: field!.format })
  })

  // Build category axis from first dimension (time -> series, else categorical values)
  let categories: string[] = ['Total']
  const firstDim = dimFields[0]
  if (firstDim) {
    if (firstDim.field!.role === 'time') {
      const grain = firstDim.d.grain ?? 'month'
      categories = timeSeries(grain, grain === 'day' ? 14 : grain === 'week' ? 12 : 12)
    } else {
      categories = DIM_VALUES[firstDim.field!.id] ?? ['A', 'B', 'C', 'D']
    }
  }

  const secondDim = dimFields[1]
  const series = secondDim ? (DIM_VALUES[secondDim.field!.id] ?? ['S1', 'S2', 'S3']).slice(0, 4) : [null]

  const rows: Record<string, CellValue>[] = []
  categories.forEach((cat, ci) => {
    series.forEach((s, si) => {
      const row: Record<string, CellValue> = {}
      if (firstDim) row[firstDim.d.alias ?? firstDim.d.fieldId] = cat
      if (secondDim && s != null) row[secondDim.d.alias ?? secondDim.d.fieldId] = s
      measFields.forEach(({ m, field }) => {
        const base = measureBase(m.fieldId)
        const key = `${query.modelId}|${m.fieldId}|${cat}|${s ?? ''}`
        const noise = 0.6 + hash(key) * 0.8
        const trend = firstDim?.field!.role === 'time' ? 1 + (ci / categories.length) * 0.5 : 1
        const seriesFactor = secondDim ? 0.5 + si * 0.3 : 1
        let v = base * noise * trend * seriesFactor
        if (field!.dataType === 'percent') v = Math.min(0.999, base * noise)
        if (field!.dataType === 'integer') v = Math.round(v)
        else if (field!.dataType !== 'percent') v = Math.round(v)
        row[m.alias ?? m.fieldId] = v
      })
      rows.push(row)
    })
  })

  const sorted = query.sorts?.length
    ? [...rows].sort((a, b) => {
        const s = query.sorts![0]
        const av = a[s.fieldId] ?? 0
        const bv = b[s.fieldId] ?? 0
        const cmp = av < bv ? -1 : av > bv ? 1 : 0
        return s.dir === 'asc' ? cmp : -cmp
      })
    : rows

  const limited = query.limit ? sorted.slice(0, query.limit) : sorted
  return {
    columns,
    rows: limited,
    totalRows: rows.length,
    freshness: model.freshness,
    simulated: true,
  }
}

export const semanticService = {
  async listModels(): Promise<SemanticModel[]> {
    await latency(120, 300)
    return MODELS
  },
  async getModel(id: string): Promise<SemanticModel | undefined> {
    await latency(100, 240)
    return MODELS.find((m) => m.id === id)
  },
  async query(q: SemanticQuery): Promise<QueryResult> {
    await latency(160, 460)
    return runQuerySync(q)
  },
}
