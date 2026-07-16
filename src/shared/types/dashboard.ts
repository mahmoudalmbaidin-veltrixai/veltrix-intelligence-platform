/**
 * Dashboard Studio domain models.
 * A dashboard has pages; each page has a grid of widgets. Widgets bind to the
 * semantic layer through a typed query + formatting + interaction config.
 */

import type { Aggregation, QueryFilter, SemanticQuery } from './semantic'

export type WidgetType =
  | 'kpi'
  | 'metric-comparison'
  | 'table'
  | 'pivot'
  | 'bar'
  | 'stacked-bar'
  | 'column'
  | 'line'
  | 'area'
  | 'pie'
  | 'donut'
  | 'scatter'
  | 'gauge'
  | 'progress'
  | 'text'
  | 'rich-text'
  | 'image'
  | 'filter'
  | 'date-filter'
  | 'map'

export interface GridPosition {
  /** Column start (0-based) on a 12-col grid. */
  x: number
  y: number
  w: number
  h: number
}

/** Field-well assignments — Power BI style visual configuration. */
export interface FieldWells {
  xAxis?: string[]
  yAxis?: string[]
  values?: WellValue[]
  legend?: string[]
  category?: string[]
  series?: string[]
  size?: string[]
  tooltip?: string[]
  details?: string[]
  smallMultiples?: string[]
  drill?: string[] // ordered drill hierarchy
}

export interface WellValue {
  fieldId: string
  aggregation: Aggregation
}

export interface ConditionalRule {
  id: string
  when: 'gt' | 'lt' | 'between' | 'eq'
  value: number
  value2?: number
  color: string
}

export interface WidgetFormat {
  title?: string
  subtitle?: string
  showTitle: boolean
  showLegend: boolean
  legendPosition: 'top' | 'right' | 'bottom' | 'left'
  showDataLabels: boolean
  showGridlines: boolean
  decimals: number
  numberStyle: 'plain' | 'currency' | 'percent' | 'compact'
  currency?: string
  background?: string
  border: boolean
  padding: number
  conditional: ConditionalRule[]
  colorScheme?: string
}

export interface WidgetInteractions {
  crossFilter: boolean
  drillDown: boolean
  drillThrough?: string // target page/dashboard id
  tooltip: boolean
  exportable: boolean
  navigateTo?: string
}

export interface WidgetGeneral {
  name: string
  description?: string
  visible: boolean
  locked: boolean
  ariaLabel?: string
}

export interface DashboardWidget {
  id: string
  type: WidgetType
  modelId?: string
  pos: GridPosition
  wells: FieldWells
  filters: QueryFilter[]
  sorts?: { fieldId: string; dir: 'asc' | 'desc' }[]
  format: WidgetFormat
  interactions: WidgetInteractions
  general: WidgetGeneral
  /** For text/image/rich widgets. */
  content?: string
}

export interface DashboardPage {
  id: string
  name: string
  widgets: DashboardWidget[]
  filters: QueryFilter[]
}

export type DashboardStatus = 'draft' | 'published'

export interface Dashboard {
  id: string
  name: string
  description: string
  status: DashboardStatus
  version: number
  owner: string
  tags: string[]
  pages: DashboardPage[]
  filters: QueryFilter[] // dashboard-global
  updatedAt: string
  favorite: boolean
  freshness: string
}

export interface DashboardListItem {
  id: string
  name: string
  status: DashboardStatus
  owner: string
  tags: string[]
  updatedAt: string
  favorite: boolean
  pageCount: number
  widgetCount: number
}

/** Build a SemanticQuery from a widget's wells + filters. */
export function toQuery(widget: DashboardWidget, extraFilters: QueryFilter[] = []): SemanticQuery {
  const dims = [
    ...(widget.wells.xAxis ?? []),
    ...(widget.wells.category ?? []),
    ...(widget.wells.legend ?? []),
    ...(widget.wells.series ?? []),
  ]
  const uniqueDims = Array.from(new Set(dims))
  const values = widget.wells.values ?? []
  const yFallback = (widget.wells.yAxis ?? []).map((fieldId) => ({ fieldId, aggregation: 'sum' as Aggregation }))
  const sizeVals = (widget.wells.size ?? []).map((fieldId) => ({ fieldId, aggregation: 'sum' as Aggregation }))
  const measures = [...values, ...yFallback, ...sizeVals]
  return {
    modelId: widget.modelId ?? '',
    dimensions: uniqueDims.map((fieldId) => ({ fieldId })),
    measures: measures.map((m) => ({ fieldId: m.fieldId, aggregation: m.aggregation })),
    filters: [...widget.filters, ...extraFilters],
    sorts: widget.sorts,
    limit: 500,
  }
}
