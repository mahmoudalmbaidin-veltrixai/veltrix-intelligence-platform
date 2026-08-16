import { describe, expect, it } from 'vitest'
import type { Dashboard, DashboardWidget, WidgetType } from '@/shared/types/dashboard'
import type { SemanticModel } from '@/shared/types/semantic'
import {
  canPublishDashboard,
  scatterConfigurationIssue,
  validateDashboardWidgets,
  validateWidgetConfiguration,
} from './widgetValidation'

const model: SemanticModel = {
  id: 'model',
  name: 'model',
  label: 'Model',
  description: '',
  entities: [],
  fields: [
    { id: 'revenue', name: 'revenue', label: 'Revenue', role: 'metric', dataType: 'currency' },
    { id: 'profit', name: 'profit', label: 'Profit', role: 'metric', dataType: 'number' },
    { id: 'label', name: 'label', label: 'Label', role: 'measure', dataType: 'string' },
  ],
  freshness: '2026-08-10T00:00:00Z',
  owner: 'QA',
  certified: true,
}

function widget(type: WidgetType, opts: { modelId?: string; values?: string[] } = {}): DashboardWidget {
  return {
    id: `w-${type}`,
    type,
    modelId: opts.modelId,
    pos: { x: 0, y: 0, w: 6, h: 5 },
    wells: { values: (opts.values ?? []).map((fieldId) => ({ fieldId, aggregation: 'sum' })) },
    filters: [],
    format: {
      showTitle: true,
      showLegend: true,
      legendPosition: 'bottom',
      showDataLabels: false,
      showGridlines: true,
      decimals: 0,
      numberStyle: 'plain',
      border: true,
      padding: 12,
      conditional: [],
    },
    interactions: { crossFilter: true, drillDown: false, tooltip: true, exportable: true },
    general: { name: type, visible: true, locked: false },
  }
}

function dashboard(widgets: DashboardWidget[]): Dashboard {
  return {
    id: 'db',
    name: 'DB',
    status: 'draft',
    version: 1,
    pages: [{ id: 'p1', name: 'Page 1', widgets, filters: [] }],
    filters: [],
    updatedAt: '2026-08-10T00:00:00Z',
  } as Dashboard
}

const scatter = (values: string[]) => widget('scatter', { modelId: model.id, values })

describe('Scatter configuration contract (back-compat)', () => {
  it('accepts ordered numeric X and Y metrics', () => {
    expect(scatterConfigurationIssue(scatter(['revenue', 'profit']), model)).toBeUndefined()
  })
  it('reports missing X and missing Y distinctly', () => {
    expect(scatterConfigurationIssue(scatter([]), model)?.code).toBe('SCATTER_X_REQUIRED')
    expect(scatterConfigurationIssue(scatter(['revenue']), model)?.code).toBe('SCATTER_Y_REQUIRED')
  })
  it('rejects a determinably non-numeric axis field', () => {
    expect(scatterConfigurationIssue(scatter(['revenue', 'label']), model)?.code).toBe('SCATTER_NUMERIC_REQUIRED')
  })
})

describe('validateWidgetConfiguration (authoritative, backend-aligned)', () => {
  it('marks a data widget with a model and a measure as valid', () => {
    expect(validateWidgetConfiguration(widget('kpi', { modelId: model.id, values: ['revenue'] })).valid).toBe(true)
  })

  it('flags a data widget with no measure', () => {
    const result = validateWidgetConfiguration(widget('bar', { modelId: model.id }))
    expect(result.valid).toBe(false)
    expect(result.missing).toContain('Add at least one measure')
  })

  it('flags a data widget with no semantic model', () => {
    const result = validateWidgetConfiguration(widget('table', { values: ['revenue'] }))
    expect(result.valid).toBe(false)
    expect(result.missing).toContain('Select a dataset or semantic model')
  })

  it('lists every missing requirement for a brand-new unconfigured widget', () => {
    const result = validateWidgetConfiguration(widget('pie'))
    expect(result.valid).toBe(false)
    expect(result.missing).toEqual(['Select a dataset or semantic model', 'Add at least one measure'])
  })

  it('requires a second numeric measure for scatter', () => {
    expect(validateWidgetConfiguration(scatter(['revenue']), model).missing).toContain('Add a numeric Y measure')
    expect(validateWidgetConfiguration(scatter(['revenue', 'profit']), model).valid).toBe(true)
    expect(validateWidgetConfiguration(scatter(['revenue', 'label']), model).missing).toContain(
      'Scatter X and Y fields must be numeric',
    )
  })

  it('treats content/filter widgets as always valid', () => {
    for (const type of ['text', 'rich-text', 'image', 'filter', 'date-filter'] as WidgetType[]) {
      expect(validateWidgetConfiguration(widget(type)).valid).toBe(true)
    }
  })
})

describe('validateDashboardWidgets', () => {
  it('returns only incomplete widgets with their missing requirements', () => {
    const good = widget('kpi', { modelId: model.id, values: ['revenue'] })
    const bad = widget('bar', { modelId: model.id })
    const issues = validateDashboardWidgets(dashboard([good, bad]), [model])
    expect(issues).toHaveLength(1)
    expect(issues[0].widgetId).toBe(bad.id)
    expect(issues[0].missing).toContain('Add at least one measure')
  })
})

describe('canPublishDashboard', () => {
  it('blocks an empty dashboard', () => {
    const readiness = canPublishDashboard(dashboard([]), [model])
    expect(readiness.ok).toBe(false)
    expect(readiness.reason).toMatch(/at least one configured widget/i)
  })

  it('blocks a dashboard with an incomplete widget', () => {
    const readiness = canPublishDashboard(dashboard([widget('bar', { modelId: model.id })]), [model])
    expect(readiness.ok).toBe(false)
    expect(readiness.reason).toMatch(/finish configuring 1 widget/i)
  })

  it('allows a dashboard whose widgets are all configured', () => {
    const readiness = canPublishDashboard(dashboard([widget('kpi', { modelId: model.id, values: ['revenue'] })]), [
      model,
    ])
    expect(readiness.ok).toBe(true)
  })
})
