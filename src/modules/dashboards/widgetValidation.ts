import type { Dashboard, DashboardWidget } from '@/shared/types/dashboard'
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

export function validateDashboardWidgets(dashboard: Dashboard, models: SemanticModel[]): WidgetConfigurationIssue[] {
  const byId = new Map(models.map((model) => [model.id, model]))
  return dashboard.pages.flatMap((page) =>
    page.widgets.flatMap((widget) => {
      const issue = scatterConfigurationIssue(widget, widget.modelId ? byId.get(widget.modelId) : undefined)
      return issue ? [issue] : []
    }),
  )
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
