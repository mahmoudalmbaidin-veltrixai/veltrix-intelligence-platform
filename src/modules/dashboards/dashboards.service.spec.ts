import { describe, expect, it } from 'vitest'
import type { DashboardWidget } from '@/shared/types/dashboard'
import { widgetFromApi, widgetToApi } from './dashboards.service'

describe('dashboard widget persistence parity', () => {
  it('round-trips every layout, filter, formatting, and interaction field', () => {
    const source: DashboardWidget = {
      id: '11111111-1111-4111-8111-111111111111',
      type: 'scatter',
      modelId: '22222222-2222-4222-8222-222222222222',
      pos: { x: 3, y: 5, w: 7, h: 6 },
      wells: { category: ['region'], values: [{ fieldId: 'revenue', aggregation: 'sum' }] },
      filters: [{ fieldId: 'region', operator: 'eq', value: 'الرياض' }],
      sorts: [{ fieldId: 'revenue', dir: 'desc' }],
      format: {
        title: 'الإيرادات',
        subtitle: 'حسب المنطقة',
        showTitle: true,
        showLegend: false,
        legendPosition: 'bottom',
        showDataLabels: true,
        showGridlines: false,
        decimals: 2,
        numberStyle: 'currency',
        currency: 'SAR',
        background: '#ffffff',
        border: false,
        padding: 18,
        conditional: [{ id: 'c1', when: 'gt', value: 10, color: '#00ff00' }],
        colorScheme: 'enterprise',
      },
      interactions: {
        crossFilter: true,
        drillDown: true,
        drillThrough: 'details',
        tooltip: false,
        exportable: true,
        navigateTo: '/dashboards/next',
      },
      general: {
        name: 'الإيرادات',
        description: 'Unicode widget',
        visible: true,
        locked: true,
        ariaLabel: 'Revenue by region',
      },
    }

    const api = widgetToApi(source)
    const restored = widgetFromApi(api)

    expect(restored.type).toBe(source.type)
    expect(restored.pos).toEqual(source.pos)
    expect(restored.filters).toEqual(source.filters)
    expect(restored.sorts).toEqual(source.sorts)
    expect(restored.format).toEqual(source.format)
    expect(restored.interactions).toEqual(source.interactions)
    expect(restored.general).toEqual(source.general)
  })
})
