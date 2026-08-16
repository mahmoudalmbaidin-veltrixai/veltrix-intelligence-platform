import type { Dashboard, DashboardWidget, WidgetType } from '@/shared/types/dashboard'
import type { SemanticModel } from '@/shared/types/semantic'

export interface WidgetConfigurationIssue {
  widgetId: string
  widgetName: string
  code: 'SCATTER_X_REQUIRED' | 'SCATTER_Y_REQUIRED' | 'SCATTER_NUMERIC_REQUIRED'
  message: string
}

const numericTypes = new Set(['number', 'integer', 'currency', 'percent'])

export function scatterConfigurationIssue(
  widget: DashboardWidget,
  model?: SemanticModel,
): WidgetConfigurationIssue | undefined {
  if (widget.type !== 'scatter') return undefined
  const values = widget.wells.values ?? []
  const x = values[0]?.fieldId
  const y = values[1]?.fieldId
  if (!x) return issue(widget, 'SCATTER_X_REQUIRED', 'Scatter requires a numeric X field.')
  if (!y) return issue(widget, 'SCATTER_Y_REQUIRED', 'Scatter requires a numeric Y field.')
  if (model) {
    const fields = new Map(model.fields.map((field) => [field.id, field]))
    if (![x, y].every((key) => numericTypes.has(fields.get(key)?.dataType ?? ''))) {
      return issue(widget, 'SCATTER_NUMERIC_REQUIRED', 'Scatter X and Y fields must be numeric.')
    }
  }
  return undefined
}

/**
 * Widget types the backend treats as "data widgets"
 * (apps/api/.../dashboards/schemas.py::validate_widget). Each requires a
 * semantic model AND at least one metric (serialized from wells.values), or the
 * PUT/publish request is rejected with HTTP 422. Content/filter widgets
 * (text, rich-text, image, filter, date-filter) carry no such requirement.
 */
export const DATA_WIDGET_TYPES: ReadonlySet<WidgetType> = new Set<WidgetType>([
  'kpi',
  'metric-comparison',
  'table',
  'pivot',
  'bar',
  'stacked-bar',
  'column',
  'line',
  'area',
  'pie',
  'donut',
  'scatter',
  'gauge',
  'progress',
  'map',
])

export function isDataWidget(type: WidgetType): boolean {
  return DATA_WIDGET_TYPES.has(type)
}

export interface WidgetValidation {
  valid: boolean
  /** Human-readable requirements still missing, in the order to address them. */
  missing: string[]
}

/**
 * Authoritative, backend-aligned completeness check for a single widget. Mirrors
 * the API contract so an obviously incomplete widget is caught in the UI before
 * it can produce a raw 422: a data widget needs a semantic model and at least
 * one measure (wells.values). Scatter additionally needs a second (Y) measure,
 * required to be numeric when the semantic model is known.
 */
export function validateWidgetConfiguration(widget: DashboardWidget, model?: SemanticModel): WidgetValidation {
  if (!isDataWidget(widget.type)) return { valid: true, missing: [] }
  const missing: string[] = []
  if (!widget.modelId) missing.push('Select a dataset or semantic model')
  const values = widget.wells.values ?? []
  if (widget.type === 'scatter') {
    if (values.length < 1) missing.push('Add a numeric X measure')
    else if (values.length < 2) missing.push('Add a numeric Y measure')
    if (model && values.length >= 2) {
      const fields = new Map(model.fields.map((field) => [field.id, field]))
      const numeric = [values[0], values[1]].every((value) =>
        numericTypes.has(fields.get(value.fieldId)?.dataType ?? ''),
      )
      if (!numeric) missing.push('Scatter X and Y fields must be numeric')
    }
  } else if (values.length < 1) {
    missing.push('Add at least one measure')
  }
  return { valid: missing.length === 0, missing }
}

export interface IncompleteWidget {
  widgetId: string
  widgetName: string
  missing: string[]
}

/**
 * All widgets that would be rejected by the backend, with the specific missing
 * requirements. Drives the save gate and the incomplete-widget messaging.
 */
export function validateDashboardWidgets(dashboard: Dashboard, models: SemanticModel[]): IncompleteWidget[] {
  const byId = new Map(models.map((model) => [model.id, model]))
  const incomplete: IncompleteWidget[] = []
  for (const page of dashboard.pages) {
    for (const widget of page.widgets) {
      const model = widget.modelId ? byId.get(widget.modelId) : undefined
      const { valid, missing } = validateWidgetConfiguration(widget, model)
      if (!valid) {
        incomplete.push({
          widgetId: widget.id,
          widgetName: widget.format.title || widget.general.name,
          missing,
        })
      }
    }
  }
  return incomplete
}

export interface PublishReadiness {
  ok: boolean
  reason?: string
}

/**
 * Single source of truth for publish eligibility (Phase 13): the dashboard must
 * have at least one widget and no incomplete data widget. Empty or partially
 * configured dashboards are unpublishable (the backend rejects them with 422).
 */
export function canPublishDashboard(dashboard: Dashboard, models: SemanticModel[]): PublishReadiness {
  const widgetCount = dashboard.pages.reduce((count, page) => count + page.widgets.length, 0)
  if (widgetCount === 0) {
    return { ok: false, reason: 'Add at least one configured widget before publishing.' }
  }
  const incomplete = validateDashboardWidgets(dashboard, models)
  if (incomplete.length > 0) {
    const noun = incomplete.length > 1 ? 'widgets' : 'widget'
    return { ok: false, reason: `Finish configuring ${incomplete.length} ${noun} before publishing.` }
  }
  return { ok: true }
}

function issue(
  widget: DashboardWidget,
  code: WidgetConfigurationIssue['code'],
  message: string,
): WidgetConfigurationIssue {
  return {
    widgetId: widget.id,
    widgetName: widget.format.title || widget.general.name,
    code,
    message,
  }
}
