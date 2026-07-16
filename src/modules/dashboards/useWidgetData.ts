/** Runs the semantic query for a widget and exposes reactive result/loading/error. */
import { ref, watch, type Ref } from 'vue'
import type { DashboardWidget } from '@/shared/types/dashboard'
import { toQuery } from '@/shared/types/dashboard'
import type { QueryFilter, QueryResult } from '@/shared/types/semantic'
import { semanticService } from '@/shared/services/semanticModels'
import { ApiError } from '@/shared/types/api'

export function useWidgetData(widget: Ref<DashboardWidget>, extraFilters: Ref<QueryFilter[]>) {
  const result = ref<QueryResult | undefined>()
  const loading = ref(false)
  const error = ref<string | undefined>()

  async function run() {
    const w = widget.value
    if (['text', 'rich-text', 'image', 'filter', 'date-filter'].includes(w.type) || !w.modelId) {
      result.value = undefined
      return
    }
    loading.value = true
    error.value = undefined
    try {
      result.value = await semanticService.query(toQuery(w, extraFilters.value))
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Query failed'
    } finally {
      loading.value = false
    }
  }

  watch(
    () => JSON.stringify([widget.value.wells, widget.value.filters, widget.value.type, widget.value.modelId, extraFilters.value]),
    run,
    { immediate: true },
  )

  return { result, loading, error, refetch: run }
}
