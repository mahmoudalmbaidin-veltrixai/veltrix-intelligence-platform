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
import { LocalStore, latency, isoAgo, nowIso, clone, currentStorageScope } from '@/shared/lib/mock'
import { ApiError } from '@/shared/types/api'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'
import { SEED_DASHBOARDS } from './seed'

// Tenant/workspace-partitioned so dashboards never leak across tenants (C002).
const store = new LocalStore<Record<string, Dashboard>>('vip.dashboards', { scoped: true })

function db(): Record<string, Dashboard> {
  const existing = store.read({})
  if (Object.keys(existing).length === 0 && currentStorageScope().startsWith('org_veltrix')) {
    // Seed demo content only in the primary tenant; other tenants start empty
    // to demonstrate isolation.
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

/**
 * Domain service contract. Views/composables depend on this interface via the
 * `dashboardService` factory export — never on a concrete implementation.
 */
export interface DashboardService {
  list(): Promise<DashboardListItem[]>
  get(id: string): Promise<Dashboard>
  save(dashboard: Dashboard): Promise<Dashboard>
  publish(dashboard: Dashboard): Promise<Dashboard>
  toggleFavorite(id: string): Promise<void>
}

const mockDashboardService: DashboardService = {
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

/**
 * Live adapter — routes through the centralized API client. Endpoint paths
 * reflect the expected backend contract (see BACKEND_INTEGRATION.md).
 */
const apiDashboardService: DashboardService = {
  list: () => apiClient.get<DashboardListItem[]>('/dashboards'),
  get: (id) => apiClient.get<Dashboard>(`/dashboards/${id}`),
  save: (dashboard) => apiClient.put<Dashboard>(`/dashboards/${dashboard.id}`, dashboard),
  publish: (dashboard) => apiClient.post<Dashboard>(`/dashboards/${dashboard.id}/publish`),
  toggleFavorite: (id) => apiClient.post<void>(`/dashboards/${id}/favorite`),
}

/** Selected by VITE_API_MODE. Views import this, not a concrete class. */
export const dashboardService: DashboardService = defineService(mockDashboardService, () => apiDashboardService)

export const LAST_REFRESH = isoAgo(35)
