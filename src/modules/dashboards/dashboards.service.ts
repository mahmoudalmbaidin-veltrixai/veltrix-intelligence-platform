/**
 * Dashboard service (mock + local persistence).
 *
 * INTEGRATION POINT
 *   GET  /api/v1/dashboards            -> DashboardListItem[]
 *   GET  /api/v1/dashboards/:id        -> Dashboard
 *   PUT  /api/v1/dashboards/:id        -> Dashboard (save draft)
 *   POST /api/v1/dashboards/:id/publish
 *   permission: dashboard:read / dashboard:write / dashboard:publish
 */
import type { Dashboard, DashboardListItem } from '@/shared/types/dashboard'
import { LocalStore, latency, isoAgo, nowIso, clone } from '@/shared/lib/mock'
import { ApiError } from '@/shared/types/api'
import { SEED_DASHBOARDS } from './seed'

const store = new LocalStore<Record<string, Dashboard>>('vip.dashboards')

function db(): Record<string, Dashboard> {
  const existing = store.read({})
  if (Object.keys(existing).length === 0) {
    const seeded: Record<string, Dashboard> = {}
    SEED_DASHBOARDS.forEach((d) => (seeded[d.id] = d))
    store.write(seeded)
    return seeded
  }
  return existing
}

export function newDashboard(): Dashboard {
  return {
    id: `db_${Math.random().toString(36).slice(2, 8)}`,
    name: 'Untitled dashboard',
    description: '',
    status: 'draft',
    version: 1,
    owner: 'You',
    tags: [],
    pages: [{ id: 'pg_1', name: 'Page 1', widgets: [], filters: [] }],
    filters: [],
    updatedAt: nowIso(),
    favorite: false,
    freshness: nowIso(),
  }
}

export const dashboardService = {
  async list(): Promise<DashboardListItem[]> {
    await latency()
    return Object.values(db())
      .map((d) => ({
        id: d.id, name: d.name, status: d.status, owner: d.owner, tags: d.tags,
        updatedAt: d.updatedAt, favorite: d.favorite, pageCount: d.pages.length,
        widgetCount: d.pages.reduce((s, p) => s + p.widgets.length, 0),
      }))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  },
  async get(id: string): Promise<Dashboard> {
    await latency(120, 320)
    if (id === 'new') return newDashboard()
    const found = db()[id]
    if (!found) throw new ApiError('not-found', `Dashboard ${id} not found`)
    return clone(found)
  },
  async save(dashboard: Dashboard): Promise<Dashboard> {
    await latency(140, 360)
    const current = db()
    const saved = { ...dashboard, updatedAt: nowIso() }
    current[saved.id] = saved
    store.write(current)
    return clone(saved)
  },
  async publish(dashboard: Dashboard): Promise<Dashboard> {
    await latency(200, 420)
    const published = { ...dashboard, status: 'published' as const, version: dashboard.version + 1, updatedAt: nowIso() }
    const current = db()
    current[published.id] = published
    store.write(current)
    return clone(published)
  },
  async toggleFavorite(id: string): Promise<void> {
    await latency(60, 140)
    const current = db()
    if (current[id]) { current[id].favorite = !current[id].favorite; store.write(current) }
  },
}

export const LAST_REFRESH = isoAgo(35)
