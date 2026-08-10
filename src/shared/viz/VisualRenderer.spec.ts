import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { DashboardWidget } from '@/shared/types/dashboard'
import type { QueryResult } from '@/shared/types/semantic'
import VisualRenderer from './VisualRenderer.vue'

const baseWidget: DashboardWidget = {
  id: 'visual',
  type: 'scatter',
  pos: { x: 0, y: 0, w: 6, h: 5 },
  wells: { values: [{ fieldId: 'x', aggregation: 'sum' }] },
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
  general: { name: 'Visual', visible: true, locked: false },
}

const matrixResult: QueryResult = {
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

describe('VisualRenderer semantic states', () => {
  it('renders an explicit invalid state for incomplete Scatter instead of another chart', () => {
    const wrapper = mount(VisualRenderer, {
      props: { widget: baseWidget, result: matrixResult },
    })

    expect(wrapper.get('[data-testid="scatter-configuration-error"]').text()).toContain(
      'Scatter requires a numeric Y field.',
    )
    expect(wrapper.findComponent({ name: 'CartesianChart' }).exists()).toBe(false)
  })

  it('renders Pivot as a matrix with deterministic row and column cells', () => {
    const pivot: DashboardWidget = {
      ...baseWidget,
      type: 'pivot',
      wells: {
        category: ['region', 'quarter'],
        values: [{ fieldId: 'revenue', aggregation: 'sum' }],
      },
    }
    const wrapper = mount(VisualRenderer, { props: { widget: pivot, result: matrixResult } })
    const text = wrapper.get('table').text()

    for (const value of ['Region', 'Q1', 'Q2', 'Region A', '111', '222', 'Region B', '333', '444']) {
      expect(text).toContain(value)
    }
  })
})
