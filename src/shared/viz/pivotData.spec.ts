import { describe, expect, it } from 'vitest'
import type { DashboardWidget } from '@/shared/types/dashboard'
import type { QueryResult } from '@/shared/types/semantic'
import { toPivotTable } from './pivotData'

const widget = {
  id: 'pivot',
  type: 'pivot',
  pos: { x: 0, y: 0, w: 6, h: 5 },
  wells: {
    category: ['region', 'quarter'],
    values: [{ fieldId: 'revenue', aggregation: 'sum' }],
  },
  filters: [],
  format: {
    showTitle: true,
    showLegend: false,
    legendPosition: 'bottom',
    showDataLabels: true,
    showGridlines: true,
    decimals: 0,
    numberStyle: 'plain',
    border: true,
    padding: 12,
    conditional: [],
  },
  interactions: { crossFilter: true, drillDown: false, tooltip: true, exportable: true },
  general: { name: 'Revenue matrix', visible: true, locked: false },
} satisfies DashboardWidget

const result: QueryResult = {
  columns: [
    { key: 'region', label: 'Region', role: 'dimension', dataType: 'string' },
    { key: 'quarter', label: 'Quarter', role: 'dimension', dataType: 'string' },
    { key: 'revenue', label: 'Revenue', role: 'metric', dataType: 'currency' },
  ],
  rows: [
    { region: 'Region A', quarter: 'Q1', revenue: 111 },
    { region: 'Region A', quarter: 'Q2', revenue: 222 },
    { region: 'Region B', quarter: 'Q1', revenue: 333 },
    { region: 'Region B', quarter: 'Q2', revenue: 444 },
  ],
  totalRows: 4,
  freshness: '2026-08-10T00:00:00Z',
  simulated: false,
}

describe('Pivot matrix projection', () => {
  it('projects row and column dimensions into known analytical cells', () => {
    const matrix = toPivotTable(widget, result)
    expect(matrix.columns.map((column) => column.label)).toEqual(['Region', 'Q1', 'Q2'])
    expect(matrix.rows).toEqual([
      { region: 'Region A', __pivot_value_0: 111, __pivot_value_1: 222 },
      { region: 'Region B', __pivot_value_0: 333, __pivot_value_1: 444 },
    ])
  })
})
