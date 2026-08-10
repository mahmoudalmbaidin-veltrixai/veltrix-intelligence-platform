/** Runs the semantic query for a widget and exposes reactive result/loading/error. */
import { ref, watch, type Ref } from 'vue'
import type { DashboardWidget } from '@/shared/types/dashboard'
import { toQuery, type Dashboard } from '@/shared/types/dashboard'
import type { QueryFilter, QueryResult } from '@/shared/types/semantic'
import { dashboardService } from './dashboards.service'
import { semanticService } from '@/shared/services/semanticModels'
import { ApiError } from '@/shared/types/api'
import { scatterConfigurationIssue } from './widgetValidation'

interface ReturnType {
  result: Ref<QueryResult | undefined>
  loading: Ref<boolean>
  error: Ref<string | undefined>
  refetch: () => Promise<void>
}
export function useWidgetData(widget: Ref<DashboardWidget>, extraFilters: Ref<QueryFilter[]>): ReturnType
export function useWidgetData(
  dashboard: Ref<Dashboard>,
  widget: Ref<DashboardWidget>,
  extraFilters: Ref<QueryFilter[]>,
  preview: Ref<boolean>,
): ReturnType
export function useWidgetData(
  first: Ref<Dashboard> | Ref<DashboardWidget>,
  second: Ref<DashboardWidget> | Ref<QueryFilter[]>,
  third?: Ref<QueryFilter[]>,
  fourth?: Ref<boolean>,
): ReturnType {
  const dashboard = third ? (first as Ref<Dashboard>) : undefined
  const widget = (third ? second : first) as Ref<DashboardWidget>
  const extraFilters = (third ?? second) as Ref<QueryFilter[]>
  const preview = fourth
  const result = ref<QueryResult | undefined>()
  const loading = ref(false)
  const error = ref<string | undefined>()

  async function run() {
    const w = widget.value
    if (scatterConfigurationIssue(w)) {
      result.value = undefined
      loading.value = false
      error.value = undefined
      return
    }
    if (['text', 'rich-text', 'image', 'filter', 'date-filter'].includes(w.type) || !w.modelId) {
      result.value = undefined
      return
    }
    loading.value = true
    error.value = undefined
    try {
      const allowedFilters = new Set([
        ...(w.wells.xAxis ?? []),
        ...(w.wells.category ?? []),
        ...(w.wells.legend ?? []),
        ...w.filters.map((item) => item.fieldId),
      ])
      const runtimeFilters = extraFilters.value.filter((item) => allowedFilters.has(item.fieldId))
      result.value = dashboard
        ? await dashboardService.queryWidget(dashboard.value, w, runtimeFilters, preview?.value ?? false)
        : await semanticService.query(toQuery(w, runtimeFilters))
    } catch (e) {
      const apiError = ApiError.from(e)
      console.error('Dashboard widget query failed', apiError.detail ?? apiError.message)
      error.value = apiError.message
    } finally {
      loading.value = false
    }
  }

  watch(
    () =>
      JSON.stringify([
        widget.value.wells,
        widget.value.filters,
        widget.value.type,
        widget.value.modelId,
        dashboard?.value.version,
        preview?.value,
        extraFilters.value,
      ]),
    run,
    { immediate: true },
  )

  return { result, loading, error, refetch: run }
}
