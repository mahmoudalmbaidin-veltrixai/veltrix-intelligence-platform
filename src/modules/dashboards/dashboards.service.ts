/** Live Dashboard Studio adapter. Mock persistence is restricted to explicit mock mode. */
import { apiClient } from '@/shared/lib/apiClient'
import { clone, isoAgo, LocalStore, nowIso } from '@/shared/lib/mock'
import { defineService } from '@/shared/services/serviceFactory'
import type { QueryFilter, QueryResult } from '@/shared/types/semantic'
import {
  toQuery,
  type Dashboard,
  type DashboardListItem,
  type DashboardWidget,
  type WidgetType,
} from '@/shared/types/dashboard'
import { semanticService } from '@/shared/services/semanticModels'
import { SEED_DASHBOARDS } from './seed'

interface ApiSummary {
  id: string
  slug: string
  name: string
  description: string
  status: 'draft' | 'published'
  owner_user_id: string
  tags: string[]
  row_version: number
  page_count: number
  widget_count: number
  updated_at: string
  published_version: number | null
}
interface ApiWidget {
  id?: string
  page_id?: string
  type: string
  title: string
  description: string
  semantic_model_id?: string | null
  query: {
    metrics: string[]
    dimensions: string[]
    filters: Array<{ field: string; operator: string; value: unknown }>
    order_by: Array<{ field: string; direction: 'asc' | 'desc' }>
    limit: number
  }
  config: Record<string, unknown>
  layout: { x: number; y: number; w: number; h: number }
  filters: Array<{ field: string; operator: string; value: unknown }>
  interactions: Record<string, unknown>
  content?: string | null
  hidden: boolean
}
interface ApiPage {
  id?: string
  key: string
  name: string
  description: string
  position: number
  canvas: Record<string, unknown>
  widgets: ApiWidget[]
}
interface ApiDashboardFilter {
  id?: string
  key: string
  label: string
  type: 'select' | 'multi_select' | 'date' | 'date_range' | 'number' | 'number_range' | 'text'
  semantic_model_id: string
  dimension_key: string
  operator: string
  default_value: unknown
  widget_ids: string[]
  position: number
}
interface ApiEditor {
  dashboard: ApiSummary
  pages: ApiPage[]
  filters: ApiDashboardFilter[]
  version: number
  etag: string
}
interface ApiViewer {
  dashboard: ApiSummary
  version: number
  snapshot: { pages: ApiPage[]; filters: ApiDashboardFilter[] }
}
interface ApiWidgetData {
  columns: QueryResult['columns']
  rows: QueryResult['rows']
  row_count: number
  execution: { executed_at: string }
}

export interface DashboardVersion {
  id: string
  version_number: number
  version_type: string
  created_by_user_id: string | null
  created_at: string
  published_at: string | null
  change_summary: string
  current_published: boolean
}

export interface DashboardShare {
  id: string
  principal_type: 'user' | 'role'
  principal_id: string
  permission_level: 'view' | 'edit'
  created_at: string
  expires_at: string | null
  revoked_at: string | null
}

export interface DashboardSnapshot {
  id: string
  dashboard_version_id: string
  name: string
  description: string
  filter_state: Record<string, unknown>
  status: string
  created_by_user_id: string | null
  created_at: string
  expires_at: string | null
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const operatorToApi: Record<string, string> = {
  eq: 'equals',
  neq: 'not_equals',
  nin: 'not_in',
  gt: 'greater_than',
  gte: 'greater_than_or_equal',
  lt: 'less_than',
  lte: 'less_than_or_equal',
  starts: 'starts_with',
  ends: 'ends_with',
}
const operatorFromApi: Record<string, QueryFilter['operator']> = {
  equals: 'eq',
  not_equals: 'neq',
  not_in: 'nin',
  greater_than: 'gt',
  greater_than_or_equal: 'gte',
  less_than: 'lt',
  less_than_or_equal: 'lte',
  starts_with: 'starts',
  ends_with: 'ends',
}

export function widgetFromApi(item: ApiWidget): DashboardWidget {
  const persistedFilters = item.filters.length ? item.filters : item.query.filters
  return {
    id: item.id!,
    type: item.type as WidgetType,
    modelId: item.semantic_model_id ?? undefined,
    pos: item.layout,
    wells: {
      xAxis: item.query.dimensions,
      values: item.query.metrics.map((fieldId) => ({ fieldId, aggregation: 'sum' })),
    },
    filters: persistedFilters.map((filter) => ({
      fieldId: filter.field,
      operator: operatorFromApi[filter.operator] ?? (filter.operator as QueryFilter['operator']),
      value: filter.value as QueryFilter['value'],
    })),
    sorts: item.query.order_by.map((sort) => ({ fieldId: sort.field, dir: sort.direction })),
    format: {
      title: item.title,
      subtitle: item.config.subtitle as string | undefined,
      showTitle: true,
      showLegend: Boolean(item.config.show_legend ?? true),
      legendPosition: (item.config.legend_position as 'top' | 'right' | 'bottom' | 'left') ?? 'right',
      showDataLabels: Boolean(item.config.show_labels ?? false),
      showGridlines: Boolean(item.config.show_gridlines ?? true),
      decimals: Number(item.config.decimals ?? 0),
      numberStyle: (item.config.number_style as 'plain' | 'currency' | 'percent' | 'compact') ?? 'plain',
      currency: item.config.currency as string | undefined,
      background: item.config.background as string | undefined,
      border: Boolean(item.config.border ?? true),
      padding: Number(item.config.padding ?? 12),
      conditional: (item.config.conditional as DashboardWidget['format']['conditional']) ?? [],
      colorScheme: item.config.color_scheme as string | undefined,
    },
    interactions: {
      crossFilter: Boolean(item.interactions.crossFilter ?? true),
      drillDown: Boolean(item.interactions.drillDown ?? false),
      drillThrough: item.interactions.drillThrough as string | undefined,
      tooltip: Boolean(item.interactions.tooltip ?? true),
      exportable: Boolean(item.interactions.exportable ?? true),
      navigateTo: item.interactions.navigateTo as string | undefined,
    },
    general: {
      name: item.title,
      description: item.description,
      visible: !item.hidden,
      locked: Boolean(item.config.locked ?? false),
      ariaLabel: item.config.aria_label as string | undefined,
    },
    content: item.content ?? undefined,
  }
}

function dashboardFromApi(
  summary: ApiSummary,
  pages: ApiPage[],
  version = summary.row_version,
  filters: ApiDashboardFilter[] = [],
): Dashboard {
  return {
    id: summary.id,
    name: summary.name,
    description: summary.description,
    status: summary.status,
    version,
    owner: summary.owner_user_id,
    tags: summary.tags,
    pages: pages.map((page) => ({
      id: page.id!,
      name: page.name,
      widgets: page.widgets.map(widgetFromApi),
      filters: [],
    })),
    filters: filters.map((item) => ({
      fieldId: item.dimension_key,
      operator: operatorFromApi[item.operator] ?? (item.operator as QueryFilter['operator']),
      value: item.default_value as QueryFilter['value'],
      label: item.label,
    })),
    updatedAt: summary.updated_at,
    favorite: false,
    freshness: summary.updated_at,
  }
}

export function widgetToApi(widget: DashboardWidget): ApiWidget {
  const dimensions = Array.from(
    new Set([...(widget.wells.xAxis ?? []), ...(widget.wells.category ?? []), ...(widget.wells.legend ?? [])]),
  )
  const metrics = (widget.wells.values ?? []).map((item) => item.fieldId)
  return {
    id: UUID.test(widget.id) ? widget.id : undefined,
    type: widget.type,
    title: widget.format.title || widget.general.name,
    description: widget.general.description ?? '',
    semantic_model_id: widget.modelId || null,
    query: {
      metrics,
      dimensions,
      filters: widget.filters.map((item) => ({
        field: item.fieldId,
        operator: operatorToApi[item.operator] ?? item.operator,
        value: item.value,
      })),
      order_by: (widget.sorts ?? []).map((item) => ({ field: item.fieldId, direction: item.dir })),
      limit: 500,
    },
    config: {
      decimals: widget.format.decimals,
      number_style: widget.format.numberStyle,
      ...(widget.format.currency ? { currency: widget.format.currency } : {}),
      show_legend: widget.format.showLegend,
      show_labels: widget.format.showDataLabels,
      show_gridlines: widget.format.showGridlines,
      legend_position: widget.format.legendPosition,
      ...(widget.format.subtitle ? { subtitle: widget.format.subtitle } : {}),
      ...(widget.format.background ? { background: widget.format.background } : {}),
      border: widget.format.border,
      padding: widget.format.padding,
      conditional: widget.format.conditional,
      locked: widget.general.locked,
      ...(widget.general.ariaLabel ? { aria_label: widget.general.ariaLabel } : {}),
      ...(widget.format.colorScheme ? { color_scheme: widget.format.colorScheme } : {}),
    },
    layout: widget.pos,
    filters: widget.filters.map((item) => ({
      field: item.fieldId,
      operator: operatorToApi[item.operator] ?? item.operator,
      value: item.value,
    })),
    interactions: {
      crossFilter: widget.interactions.crossFilter,
      drillDown: widget.interactions.drillDown,
      ...(widget.interactions.drillThrough ? { drillThrough: widget.interactions.drillThrough } : {}),
      tooltip: widget.interactions.tooltip,
      exportable: widget.interactions.exportable,
      ...(widget.interactions.navigateTo ? { navigateTo: widget.interactions.navigateTo } : {}),
    },
    content: widget.content,
    hidden: !widget.general.visible,
  }
}

export function newDashboard(): Dashboard {
  return {
    id: 'new',
    name: 'Untitled dashboard',
    description: '',
    status: 'draft',
    version: 1,
    owner: 'You',
    tags: [],
    pages: [{ id: 'new-page', name: 'Page 1', widgets: [], filters: [] }],
    filters: [],
    updatedAt: nowIso(),
    favorite: false,
    freshness: nowIso(),
  }
}

export interface DashboardService {
  list(): Promise<DashboardListItem[]>
  get(id: string): Promise<Dashboard>
  getPublished(id: string): Promise<Dashboard>
  rowVersion(id: string): Promise<number>
  save(dashboard: Dashboard): Promise<Dashboard>
  publish(dashboard: Dashboard): Promise<Dashboard>
  versions(id: string): Promise<DashboardVersion[]>
  restore(id: string, versionId: string, expectedVersion: number): Promise<Dashboard>
  shares(id: string): Promise<DashboardShare[]>
  createShare(
    id: string,
    expectedVersion: number,
    principalType: 'user' | 'role',
    principalId: string,
    permissionLevel: 'view' | 'edit',
  ): Promise<DashboardShare>
  revokeShare(id: string, shareId: string, expectedVersion: number): Promise<void>
  snapshots(id: string): Promise<DashboardSnapshot[]>
  createSnapshot(id: string, name: string): Promise<DashboardSnapshot>
  duplicate(id: string): Promise<Dashboard>
  rename(id: string, name: string): Promise<Dashboard>
  archive(id: string, expectedVersion: number): Promise<void>
  delete(id: string, expectedVersion: number): Promise<void>
  toggleFavorite(id: string): Promise<void>
  queryWidget(
    dashboard: Dashboard,
    widget: DashboardWidget,
    filters: QueryFilter[],
    preview: boolean,
  ): Promise<QueryResult>
}

const apiDashboardService: DashboardService = {
  async list() {
    const rows = await apiClient.get<ApiSummary[]>('/dashboards')
    return rows.map((item) => ({
      id: item.id,
      name: item.name,
      status: item.status,
      owner: item.owner_user_id,
      tags: item.tags,
      updatedAt: item.updated_at,
      favorite: false,
      pageCount: item.page_count,
      widgetCount: item.widget_count,
    }))
  },
  async get(id) {
    const result = await apiClient.get<ApiEditor>(`/dashboards/${id}/editor`)
    return dashboardFromApi(result.dashboard, result.pages, result.version, result.filters)
  },
  async getPublished(id) {
    const result = await apiClient.get<ApiViewer>(`/dashboards/${id}/viewer`)
    return dashboardFromApi(result.dashboard, result.snapshot.pages, result.version, result.snapshot.filters)
  },
  async rowVersion(id) {
    return (await apiClient.get<ApiSummary>(`/dashboards/${id}`)).row_version
  },
  async save(value) {
    let dashboard = value
    if (!UUID.test(dashboard.id)) {
      const created = await apiClient.post<ApiSummary>('/dashboards', {
        name: dashboard.name,
        description: dashboard.description,
        tags: dashboard.tags,
      })
      dashboard = { ...dashboard, id: created.id, version: created.row_version }
    }
    const pages: ApiPage[] = dashboard.pages.map((page, position) => ({
      id: UUID.test(page.id) ? page.id : undefined,
      key: `page_${position + 1}`,
      name: page.name,
      description: '',
      position,
      canvas: {},
      widgets: page.widgets.map(widgetToApi),
    }))
    const filters: ApiDashboardFilter[] = dashboard.filters.flatMap((filter, position) => {
      const widgets = dashboard.pages
        .flatMap((page) => page.widgets)
        .filter(
          (widget) =>
            widget.modelId &&
            [...(widget.wells.xAxis ?? []), ...(widget.wells.category ?? []), ...(widget.wells.legend ?? [])].includes(
              filter.fieldId,
            ),
        )
      const semanticModelId = widgets[0]?.modelId
      if (!semanticModelId) return []
      return [
        {
          key: `filter_${position + 1}_${filter.fieldId}`.replace(/[^a-z0-9_]/gi, '_').toLowerCase(),
          label: filter.label ?? filter.fieldId,
          type: 'text',
          semantic_model_id: semanticModelId,
          dimension_key: filter.fieldId,
          operator: operatorToApi[filter.operator] ?? filter.operator,
          default_value: filter.value,
          widget_ids: widgets.map((widget) => widget.id).filter((id) => UUID.test(id)),
          position,
        },
      ]
    })
    const result = await apiClient.put<ApiEditor>(`/dashboards/${dashboard.id}/editor`, {
      expected_version: dashboard.version,
      name: dashboard.name,
      description: dashboard.description,
      tags: dashboard.tags,
      pages,
      filters,
      change_summary: 'Dashboard Studio save',
    })
    return dashboardFromApi(result.dashboard, result.pages, result.version, result.filters)
  },
  async publish(dashboard) {
    await apiClient.post(`/dashboards/${dashboard.id}/publish`, {
      expected_version: dashboard.version,
      change_summary: 'Published from Dashboard Studio',
    })
    return this.get(dashboard.id)
  },
  versions(id) {
    return apiClient.get<DashboardVersion[]>(`/dashboards/${id}/versions`)
  },
  async restore(id, versionId, expectedVersion) {
    const result = await apiClient.post<ApiEditor>(`/dashboards/${id}/versions/${versionId}/restore`, {
      expected_version: expectedVersion,
      change_summary: 'Restored from Dashboard Studio',
    })
    return dashboardFromApi(result.dashboard, result.pages, result.version, result.filters)
  },
  shares(id) {
    return apiClient.get<DashboardShare[]>(`/dashboards/${id}/shares`)
  },
  createShare(id, expectedVersion, principalType, principalId, permissionLevel) {
    return apiClient.post<DashboardShare>(`/dashboards/${id}/shares`, {
      expected_version: expectedVersion,
      principal_type: principalType,
      principal_id: principalId,
      permission_level: permissionLevel,
      expires_at: null,
    })
  },
  revokeShare(id, shareId, expectedVersion) {
    return apiClient.delete(`/dashboards/${id}/shares/${shareId}?expected_version=${expectedVersion}`)
  },
  snapshots(id) {
    return apiClient.get<DashboardSnapshot[]>(`/dashboards/${id}/snapshots`)
  },
  createSnapshot(id, name) {
    return apiClient.post<DashboardSnapshot>(`/dashboards/${id}/snapshots`, {
      name,
      description: '',
      filter_state: {},
    })
  },
  async duplicate(id) {
    const source = await this.get(id)
    const duplicate: Dashboard = {
      ...clone(source),
      id: 'new',
      name: `${source.name} copy`,
      status: 'draft',
      version: 1,
      pages: source.pages.map((page) => ({
        ...page,
        id: 'new-page',
        widgets: page.widgets.map((widget) => ({ ...widget, id: `new-${crypto.randomUUID()}` })),
      })),
    }
    return this.save(duplicate)
  },
  async rename(id, name) {
    const dashboard = await this.get(id)
    dashboard.name = name.trim()
    return this.save(dashboard)
  },
  archive(id, expectedVersion) {
    return apiClient.post(`/dashboards/${id}/archive?expected_version=${expectedVersion}`)
  },
  delete(id, expectedVersion) {
    return apiClient.delete(`/dashboards/${id}?expected_version=${expectedVersion}`)
  },
  async toggleFavorite() {
    // Favorites are intentionally not part of the B6 server aggregate.
  },
  async queryWidget(dashboard, widget, filters, preview) {
    // Editor previews must execute the definition currently on the canvas. A new
    // or dirty widget does not exist in the persisted dashboard aggregate yet,
    // so asking the immutable viewer endpoint for it would either return stale
    // data or a validation error. This still uses the governed production
    // semantic-query API; published viewing continues through the versioned
    // dashboard widget endpoint below.
    if (preview) return semanticService.query(toQuery(widget, filters))
    const result = await apiClient.post<ApiWidgetData>(`/dashboards/${dashboard.id}/widgets/${widget.id}/data`, {
      dashboard_version: dashboard.version,
      preview: false,
      filters: Object.fromEntries(filters.map((item) => [item.fieldId, item.value])),
      limit_override: null,
    })
    return {
      columns: result.columns,
      rows: result.rows,
      totalRows: result.row_count,
      freshness: result.execution.executed_at,
      simulated: false,
    }
  },
}

const mockStore = new LocalStore<Dashboard[]>('vip.dashboards', { scoped: true })
const mockRows = () => mockStore.read(clone(SEED_DASHBOARDS))
const mockDashboardService: DashboardService = {
  async list() {
    return mockRows().map((item) => ({
      id: item.id,
      name: item.name,
      status: item.status,
      owner: item.owner,
      tags: item.tags,
      updatedAt: item.updatedAt,
      favorite: item.favorite,
      pageCount: item.pages.length,
      widgetCount: item.pages.reduce((count, page) => count + page.widgets.length, 0),
    }))
  },
  async get(id) {
    return clone(mockRows().find((item) => item.id === id) ?? newDashboard())
  },
  async getPublished(id) {
    return this.get(id)
  },
  async rowVersion(id) {
    return (await this.get(id)).version
  },
  async save(dashboard) {
    const saved = clone(dashboard)
    if (!saved.id || saved.id === 'new') saved.id = `db_${Date.now().toString(36)}`
    saved.updatedAt = nowIso()
    const rows = mockRows()
    const index = rows.findIndex((item) => item.id === saved.id)
    if (index >= 0) rows[index] = clone(saved)
    else rows.unshift(clone(saved))
    mockStore.write(rows)
    return saved
  },
  async publish(dashboard) {
    return { ...clone(dashboard), status: 'published' }
  },
  async versions() {
    return []
  },
  async restore(_id, _versionId, _expectedVersion) {
    throw new Error('Version restore requires the live API')
  },
  async shares() {
    return []
  },
  async createShare() {
    throw new Error('Dashboard sharing requires the live API')
  },
  async revokeShare() {},
  async snapshots() {
    return []
  },
  async createSnapshot() {
    throw new Error('Dashboard snapshots require the live API')
  },
  async duplicate(id) {
    const source = await this.get(id)
    return this.save({
      ...source,
      id: 'new',
      name: `${source.name} copy`,
      status: 'draft',
      pages: source.pages.map((page) => ({
        ...page,
        id: `page_${Date.now().toString(36)}`,
        widgets: page.widgets.map((widget) => ({ ...widget, id: `w_${Math.random().toString(36).slice(2)}` })),
      })),
    })
  },
  async rename(id, name) {
    const source = await this.get(id)
    return this.save({ ...source, name })
  },
  async archive(id) {
    const rows = mockRows().filter((item) => item.id !== id)
    mockStore.write(rows)
  },
  async delete(id) {
    await this.archive(id, 1)
  },
  async toggleFavorite() {},
  async queryWidget(_dashboard, widget, filters) {
    return semanticService.query(toQuery(widget, filters))
  },
}

export const dashboardService = defineService(mockDashboardService, () => apiDashboardService)
export const LAST_REFRESH = isoAgo(35)
