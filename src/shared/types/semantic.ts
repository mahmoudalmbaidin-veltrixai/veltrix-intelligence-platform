/**
 * Semantic layer + query contracts.
 *
 * The frontend NEVER talks SQL. Widgets, insights and the exploration
 * workspace describe what they want with a typed `SemanticQuery` and receive
 * a typed `QueryResult`. Mock adapters synthesise results today; the same
 * contract will be served by the backend semantic engine later.
 */

export type FieldRole = 'dimension' | 'measure' | 'metric' | 'time'
export type DataType =
  'string' | 'number' | 'integer' | 'currency' | 'percent' | 'boolean' | 'date' | 'datetime' | 'geo'

export type Aggregation = 'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct' | 'median' | 'none'

export interface SemanticField {
  id: string
  name: string
  label: string
  role: FieldRole
  dataType: DataType
  description?: string
  /** For measures/metrics: default aggregation. */
  defaultAggregation?: Aggregation
  /** For time fields: available grains. */
  grains?: TimeGrain[]
  /** Membership of a drill hierarchy (ordered levels share a hierarchyId). */
  hierarchyId?: string
  hierarchyLevel?: number
  format?: NumberFormat
  sensitive?: boolean
  folder?: string
}

export type TimeGrain = 'day' | 'week' | 'month' | 'quarter' | 'year'

export interface SemanticEntity {
  id: string
  name: string
  label: string
  fields: SemanticField[]
}

export interface SemanticModel {
  id: string
  name: string
  label: string
  description: string
  entities: SemanticEntity[]
  /** Convenience: flattened field list. */
  fields: SemanticField[]
  freshness: string // ISO timestamp of last data refresh
  owner: string
  certified: boolean
}

export interface NumberFormat {
  style: 'plain' | 'currency' | 'percent' | 'compact'
  currency?: string
  decimals?: number
  prefix?: string
  suffix?: string
}

/* ---------------- Query contract ---------------- */

export interface QueryMeasure {
  fieldId: string
  aggregation?: Aggregation
  alias?: string
}

export interface QueryDimension {
  fieldId: string
  grain?: TimeGrain
  alias?: string
}

export type FilterOperator =
  | 'eq'
  | 'neq'
  | 'in'
  | 'nin'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'contains'
  | 'starts'
  | 'ends'
  | 'is-null'
  | 'is-not-null'
  | 'relative-date'

export interface QueryFilter {
  fieldId: string
  operator: FilterOperator
  value: string | number | boolean | Array<string | number | boolean | null> | null
  /** Human label for chips. */
  label?: string
}

export interface QuerySort {
  fieldId: string
  dir: 'asc' | 'desc'
}

export interface SemanticQuery {
  modelId: string
  measures: QueryMeasure[]
  dimensions: QueryDimension[]
  filters: QueryFilter[]
  sorts?: QuerySort[]
  limit?: number
}

export interface QueryColumn {
  key: string
  label: string
  role: FieldRole
  dataType: DataType
  format?: NumberFormat
}

export type CellValue = string | number | boolean | null

export interface QueryResult {
  columns: QueryColumn[]
  rows: Record<string, CellValue>[]
  /** Total before limit (for "showing N of M"). */
  totalRows: number
  /** Simulated freshness for the underlying model. */
  freshness: string
  /** True when result is generated/simulated in dev. */
  simulated: boolean
}
