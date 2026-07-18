/** Widget defaults + catalog for the Dashboard Studio. */
import type { DashboardWidget, WidgetFormat, WidgetType } from '@/shared/types/dashboard'

export interface WidgetCatalogItem {
  type: WidgetType
  label: string
  icon: string
  group: 'KPI' | 'Chart' | 'Table' | 'Content' | 'Filter'
  defaultW: number
  defaultH: number
}

export const WIDGET_CATALOG: WidgetCatalogItem[] = [
  { type: 'kpi', label: 'KPI Card', icon: 'target', group: 'KPI', defaultW: 3, defaultH: 3 },
  { type: 'metric-comparison', label: 'Metric Comparison', icon: 'trendUp', group: 'KPI', defaultW: 4, defaultH: 3 },
  { type: 'gauge', label: 'Gauge', icon: 'gauge', group: 'KPI', defaultW: 3, defaultH: 4 },
  { type: 'progress', label: 'Progress', icon: 'activity', group: 'KPI', defaultW: 3, defaultH: 2 },
  { type: 'bar', label: 'Bar Chart', icon: 'chart', group: 'Chart', defaultW: 6, defaultH: 5 },
  { type: 'column', label: 'Column Chart', icon: 'chart', group: 'Chart', defaultW: 6, defaultH: 5 },
  { type: 'stacked-bar', label: 'Stacked Bar', icon: 'chart', group: 'Chart', defaultW: 6, defaultH: 5 },
  { type: 'line', label: 'Line Chart', icon: 'trendUp', group: 'Chart', defaultW: 6, defaultH: 5 },
  { type: 'area', label: 'Area Chart', icon: 'trendUp', group: 'Chart', defaultW: 6, defaultH: 5 },
  { type: 'pie', label: 'Pie Chart', icon: 'pieChart', group: 'Chart', defaultW: 4, defaultH: 5 },
  { type: 'donut', label: 'Donut Chart', icon: 'pieChart', group: 'Chart', defaultW: 4, defaultH: 5 },
  { type: 'scatter', label: 'Scatter Plot', icon: 'scatter', group: 'Chart', defaultW: 6, defaultH: 5 },
  { type: 'table', label: 'Table', icon: 'table', group: 'Table', defaultW: 6, defaultH: 5 },
  { type: 'pivot', label: 'Pivot Table', icon: 'grid', group: 'Table', defaultW: 6, defaultH: 5 },
  { type: 'text', label: 'Text', icon: 'text', group: 'Content', defaultW: 4, defaultH: 2 },
  { type: 'rich-text', label: 'Rich Content', icon: 'text', group: 'Content', defaultW: 4, defaultH: 3 },
  { type: 'image', label: 'Image', icon: 'image', group: 'Content', defaultW: 4, defaultH: 4 },
  { type: 'filter', label: 'Filter Control', icon: 'filter', group: 'Filter', defaultW: 3, defaultH: 2 },
  { type: 'date-filter', label: 'Date Range', icon: 'calendar', group: 'Filter', defaultW: 3, defaultH: 2 },
  { type: 'map', label: 'Map', icon: 'target', group: 'Chart', defaultW: 6, defaultH: 5 },
]

export function defaultFormat(): WidgetFormat {
  return {
    showTitle: true,
    showLegend: true,
    legendPosition: 'bottom',
    showDataLabels: false,
    showGridlines: true,
    decimals: 0,
    numberStyle: 'compact',
    border: true,
    padding: 12,
    conditional: [],
    colorScheme: 'default',
  }
}

let wid = 0
export function createWidget(type: WidgetType, x: number, y: number, modelId = 'sm_sales'): DashboardWidget {
  const cat = WIDGET_CATALOG.find((c) => c.type === type)!
  wid += 1
  const id = `w_${Date.now().toString(36)}${wid}`
  const wells: DashboardWidget['wells'] = {}

  // sensible starter field wells so a new widget renders immediately
  if (['bar', 'column', 'stacked-bar', 'line', 'area'].includes(type)) {
    wells.xAxis = ['region']
    wells.values = [{ fieldId: 'revenue', aggregation: 'sum' }]
    if (type === 'stacked-bar') wells.legend = ['channel']
  } else if (type === 'pie' || type === 'donut') {
    wells.category = ['category']
    wells.values = [{ fieldId: 'revenue', aggregation: 'sum' }]
  } else if (type === 'scatter') {
    wells.category = ['category']
    wells.values = [
      { fieldId: 'revenue', aggregation: 'sum' },
      { fieldId: 'profit', aggregation: 'sum' },
    ]
  } else if (['kpi', 'metric-comparison', 'gauge', 'progress'].includes(type)) {
    wells.values = [{ fieldId: 'revenue', aggregation: 'sum' }]
  } else if (type === 'table' || type === 'pivot') {
    wells.category = ['region', 'category']
    wells.values = [
      { fieldId: 'revenue', aggregation: 'sum' },
      { fieldId: 'orders', aggregation: 'sum' },
    ]
  }

  const contentDefault =
    type === 'text' || type === 'rich-text' ? 'New text block' : type === 'image' ? 'Image placeholder' : undefined

  return {
    id,
    type,
    modelId: ['text', 'rich-text', 'image'].includes(type) ? undefined : modelId,
    pos: { x, y, w: cat.defaultW, h: cat.defaultH },
    wells,
    filters: [],
    format: { ...defaultFormat(), numberStyle: type === 'kpi' ? 'currency' : 'compact', currency: 'USD' },
    interactions: { crossFilter: true, drillDown: true, tooltip: true, exportable: true },
    general: { name: cat.label, visible: true, locked: false },
    content: contentDefault,
  }
}
