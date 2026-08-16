import { describe, expect, it } from 'vitest'
import type { DashboardWidget } from '@/shared/types/dashboard'
import {
  dashboardFromPublishedApi,
  parsePublishedDashboardViewer,
  widgetFromApi,
  widgetToApi,
} from './dashboards.service'

describe('dashboard widget persistence parity', () => {
  it('round-trips every layout, filter, formatting, and interaction field', () => {
    const source: DashboardWidget = {
      id: '11111111-1111-4111-8111-111111111111',
      type: 'scatter',
      modelId: '22222222-2222-4222-8222-222222222222',
      pos: { x: 3, y: 5, w: 7, h: 6 },
      wells: {
        category: ['region'],
        values: [
          { fieldId: 'revenue', aggregation: 'sum' },
          { fieldId: 'profit', aggregation: 'sum' },
        ],
      },
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
    expect(restored.wells).toEqual(source.wells)
    expect(restored.filters).toEqual(source.filters)
    expect(restored.sorts).toEqual(source.sorts)
    expect(restored.format).toEqual(source.format)
    expect(restored.interactions).toEqual(source.interactions)
    expect(restored.general).toEqual(source.general)
  })
})

describe('published dashboard viewer contract', () => {
  it('parses the canonical response and preserves heterogeneous widgets and filters', () => {
    const pageId = '11111111-1111-4111-8111-111111111111'
    const modelId = '22222222-2222-4222-8222-222222222222'
    const widgetTypes = ['kpi', 'table', 'bar', 'line', 'pivot', 'scatter'] as const
    const widgets = widgetTypes.map((type, index) => ({
      id: `33333333-3333-4333-8333-33333333333${index}`,
      page_id: pageId,
      type,
      title: `${type} widget`,
      description: '',
      semantic_model_id: modelId,
      query: {
        metrics: type === 'scatter' ? ['revenue', 'profit'] : ['revenue'],
        dimensions: type === 'kpi' ? [] : ['region'],
        filters: [],
        order_by: [],
        limit: 100,
      },
      config: { decimals: 2, number_style: 'currency', currency: 'SAR' },
      layout: { x: (index % 2) * 6, y: Math.floor(index / 2) * 4, w: 6, h: 4 },
      filters: [],
      interactions: {},
      hidden: false,
    }))
    const identity = {
      id: '44444444-4444-4444-8444-444444444444',
      slug: 'published-contract',
      name: 'Published contract',
      description: '',
      tags: ['certified'],
    }
    const response = parsePublishedDashboardViewer({
      dashboard: {
        ...identity,
        status: 'published',
        owner_user_id: '55555555-5555-4555-8555-555555555555',
        published_at: '2026-08-16T09:00:00Z',
      },
      version: 7,
      snapshot: {
        schema_version: 1,
        dashboard: identity,
        pages: [
          {
            id: pageId,
            key: 'overview',
            name: 'Overview',
            description: '',
            position: 0,
            canvas: {},
            widgets,
          },
        ],
        filters: [
          {
            id: '66666666-6666-4666-8666-666666666666',
            key: 'order_date',
            label: 'Order date',
            type: 'date_range',
            semantic_model_id: modelId,
            dimension_key: 'order_date',
            operator: 'between',
            default_value: ['2024-01-01', '2026-12-31'],
            widget_ids: widgets.map((widget) => widget.id),
            position: 0,
          },
          {
            id: '77777777-7777-4777-8777-777777777777',
            key: 'region',
            label: 'Region',
            type: 'multi_select',
            semantic_model_id: modelId,
            dimension_key: 'region',
            operator: 'in',
            default_value: ['Riyadh', 'Jeddah'],
            widget_ids: widgets.map((widget) => widget.id),
            position: 1,
          },
        ],
      },
      access: {
        can_view: true,
        can_interact: true,
        can_edit: false,
        can_publish: false,
        can_manage_sharing: false,
        can_snapshot: false,
      },
    })

    const dashboard = dashboardFromPublishedApi(response)
    expect(dashboard.name).toBe('Published contract')
    expect(dashboard.version).toBe(7)
    expect(dashboard.updatedAt).toBe('2026-08-16T09:00:00Z')
    expect(dashboard.pages[0]?.widgets.map((widget) => widget.type)).toEqual(widgetTypes)
    expect(dashboard.filters).toEqual([
      {
        fieldId: 'order_date',
        operator: 'between',
        value: ['2024-01-01', '2026-12-31'],
        label: 'Order date',
      },
      { fieldId: 'region', operator: 'in', value: ['Riyadh', 'Jeddah'], label: 'Region' },
    ])
  })

  it('accepts nullable or omitted widget fields but rejects undeclared viewer data', () => {
    const base = {
      dashboard: {
        id: '44444444-4444-4444-8444-444444444444',
        slug: 'optional-contract',
        name: 'Optional contract',
        description: '',
        tags: [],
        status: 'published',
        owner_user_id: '55555555-5555-4555-8555-555555555555',
        published_at: '2026-08-16T09:00:00Z',
      },
      version: 1,
      snapshot: {
        schema_version: 1,
        dashboard: {
          id: '44444444-4444-4444-8444-444444444444',
          slug: 'optional-contract',
          name: 'Optional contract',
          description: '',
          tags: [],
        },
        pages: [
          {
            id: '11111111-1111-4111-8111-111111111111',
            key: 'overview',
            name: 'Overview',
            description: '',
            position: 0,
            canvas: {},
            widgets: [
              {
                id: '33333333-3333-4333-8333-333333333333',
                page_id: '11111111-1111-4111-8111-111111111111',
                type: 'text',
                title: 'Narrative',
                description: '',
                query: { metrics: [], dimensions: [], filters: [], order_by: [], limit: 100 },
                config: {},
                layout: { x: 0, y: 0, w: 12, h: 3 },
                filters: [],
                interactions: {},
                hidden: false,
              },
            ],
          },
        ],
        filters: [],
      },
      access: {
        can_view: true,
        can_interact: false,
        can_edit: false,
        can_publish: false,
        can_manage_sharing: false,
        can_snapshot: false,
      },
    }

    expect(() => parsePublishedDashboardViewer(base)).not.toThrow()
    expect(() => parsePublishedDashboardViewer({ ...base, connection_password: 'forbidden' })).toThrow()
  })
})
