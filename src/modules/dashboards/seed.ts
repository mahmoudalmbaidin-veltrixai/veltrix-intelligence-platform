import type { Dashboard } from '@/shared/types/dashboard'
import { createWidget } from './widgetFactory'
import { isoAgo } from '@/shared/lib/mock'

function w(type: Parameters<typeof createWidget>[0], x: number, y: number, wsize: number, h: number, over: Partial<ReturnType<typeof createWidget>> = {}) {
  const widget = createWidget(type, x, y)
  widget.pos.w = wsize
  widget.pos.h = h
  return { ...widget, ...over }
}

const execWidgets = [
  w('kpi', 0, 0, 3, 3, { general: { name: 'Total Revenue', visible: true, locked: false } }),
  w('kpi', 3, 0, 3, 3, { general: { name: 'Total Profit', visible: true, locked: false } }),
  w('metric-comparison', 6, 0, 3, 3, { general: { name: 'Revenue vs Target', visible: true, locked: false } }),
  w('gauge', 9, 0, 3, 3, { general: { name: 'Margin %', visible: true, locked: false } }),
  w('line', 0, 3, 8, 5, { general: { name: 'Revenue Trend', visible: true, locked: false } }),
  w('donut', 8, 3, 4, 5, { general: { name: 'Revenue by Category', visible: true, locked: false } }),
  w('column', 0, 8, 6, 5, { general: { name: 'Revenue by Region', visible: true, locked: false } }),
  w('table', 6, 8, 6, 5, { general: { name: 'Detail Breakdown', visible: true, locked: false } }),
]

export const SEED_DASHBOARDS: Dashboard[] = [
  {
    id: 'db_exec',
    name: 'Executive Overview',
    description: 'Company-wide revenue, profit and margin at a glance.',
    status: 'published',
    version: 5,
    owner: 'A. Rahman',
    tags: ['executive', 'finance'],
    pages: [
      { id: 'pg_1', name: 'Summary', widgets: execWidgets, filters: [] },
      { id: 'pg_2', name: 'Regional', widgets: [w('bar', 0, 0, 6, 5), w('pie', 6, 0, 6, 5)], filters: [] },
    ],
    filters: [],
    updatedAt: isoAgo(24),
    favorite: true,
    freshness: isoAgo(35),
  },
  {
    id: 'db_revops',
    name: 'Revenue Operations',
    description: 'Pipeline, channel performance and order velocity.',
    status: 'published',
    version: 3,
    owner: 'Revenue Ops',
    tags: ['revops', 'sales'],
    pages: [{ id: 'pg_1', name: 'Overview', widgets: [w('stacked-bar', 0, 0, 8, 5), w('kpi', 8, 0, 4, 3), w('area', 0, 5, 12, 5)], filters: [] }],
    filters: [],
    updatedAt: isoAgo(180),
    favorite: false,
    freshness: isoAgo(90),
  },
  {
    id: 'db_ops',
    name: 'Platform Health',
    description: 'Service traffic, reliability and latency.',
    status: 'draft',
    version: 1,
    owner: 'You',
    tags: ['ops', 'draft'],
    pages: [{ id: 'pg_1', name: 'Page 1', widgets: [w('line', 0, 0, 8, 5, { modelId: 'sm_ops' })], filters: [] }],
    filters: [],
    updatedAt: isoAgo(20),
    favorite: false,
    freshness: isoAgo(10),
  },
]
