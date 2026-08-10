import { describe, expect, it } from 'vitest'
import type { DashboardWidget } from '@/shared/types/dashboard'
import type { SemanticModel } from '@/shared/types/semantic'
import { scatterConfigurationIssue } from './widgetValidation'

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

function scatter(values: string[]): DashboardWidget {
  return {
    id: 'scatter',
    type: 'scatter',
    modelId: model.id,
    pos: { x: 0, y: 0, w: 6, h: 5 },
    wells: { values: values.map((fieldId) => ({ fieldId, aggregation: 'sum' })) },
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
    general: { name: 'Scatter', visible: true, locked: false },
  }
}

describe('Scatter configuration contract', () => {
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
