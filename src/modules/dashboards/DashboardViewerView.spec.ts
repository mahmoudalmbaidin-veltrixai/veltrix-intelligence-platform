import { createPinia } from 'pinia'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Dashboard, DashboardWidget, WidgetType } from '@/shared/types/dashboard'

const mocks = vi.hoisted(() => ({
  getPublished: vi.fn(),
  listModels: vi.fn(),
  push: vi.fn(),
  pushToast: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'dashboard-1' } }),
  useRouter: () => ({ push: mocks.push }),
}))
vi.mock('./dashboards.service', () => ({
  dashboardService: { getPublished: mocks.getPublished, toggleFavorite: vi.fn() },
  LAST_REFRESH: '2026-08-16T09:00:00Z',
}))
vi.mock('@/modules/semantic/semantic.service', () => ({
  semanticStudioService: { listModels: mocks.listModels },
}))
vi.mock('@/shared/stores/platform', () => ({
  usePlatformStore: () => ({ can: () => false }),
}))
vi.mock('@/shared/stores/ui', () => ({
  useUiStore: () => ({ pushToast: mocks.pushToast }),
}))

import DashboardViewerView from './DashboardViewerView.vue'

enableAutoUnmount(afterEach)

function widget(type: WidgetType, index: number): DashboardWidget {
  return {
    id: `widget-${index}`,
    type,
    modelId: 'model-1',
    pos: { x: (index % 2) * 6, y: Math.floor(index / 2) * 4, w: 6, h: 4 },
    wells: { values: [{ fieldId: 'revenue', aggregation: 'sum' }] },
    filters: [],
    format: {
      title: `${type} widget`,
      showTitle: true,
      showLegend: true,
      legendPosition: 'right',
      showDataLabels: false,
      showGridlines: true,
      decimals: 2,
      numberStyle: 'currency',
      currency: 'SAR',
      border: true,
      padding: 12,
      conditional: [],
    },
    interactions: { crossFilter: true, drillDown: false, tooltip: true, exportable: true },
    general: { name: `${type} widget`, visible: true, locked: false },
  }
}

describe('Published Dashboard Viewer rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const types: WidgetType[] = ['kpi', 'table', 'bar', 'line', 'pivot', 'scatter']
    const dashboard: Dashboard = {
      id: 'dashboard-1',
      name: 'Published contract',
      description: '',
      status: 'published',
      version: 7,
      owner: 'owner-1',
      tags: [],
      pages: [{ id: 'page-1', name: 'Overview', widgets: types.map(widget), filters: [] }],
      filters: [
        { fieldId: 'order_date', operator: 'between', value: ['2024-01-01', '2026-12-31'] },
        { fieldId: 'region', operator: 'in', value: ['Riyadh', 'Jeddah'] },
      ],
      updatedAt: '2026-08-16T09:00:00Z',
      favorite: false,
      freshness: '2026-08-16T09:00:00Z',
    }
    mocks.getPublished.mockResolvedValue(dashboard)
    mocks.listModels.mockResolvedValue([])
  })

  it('hydrates representative widgets and viewer filters without editor mode', async () => {
    const wrapper = shallowMount(DashboardViewerView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Published contract')
    expect(wrapper.findComponent({ name: 'VipBadge' }).props('tone')).toBe('success')
    const canvas = wrapper.findComponent({ name: 'DashboardGridCanvas' })
    const filterBar = wrapper.findComponent({ name: 'DashboardFilterBar' })
    expect(canvas.exists()).toBe(true)
    expect(canvas.props('editable')).toBe(false)
    expect(canvas.props('editor').dashboard.pages[0].widgets).toHaveLength(6)
    expect(filterBar.props('filters')).toHaveLength(2)
    expect(filterBar.props('filters')[0].operator).toBe('between')
  })
})
