/**
 * Dashboard delivery + snapshot service (mock + local persistence).
 *
 * INTEGRATION POINT
 *   GET/POST /api/v1/dashboards/:id/deliveries   -> ScheduledDelivery[]
 *   POST     /api/v1/dashboards/:id/snapshots     -> Snapshot
 *   POST     /api/v1/dashboards/:id/export        -> { url } (server-rendered PDF/PNG)
 *   permission: dashboard:share
 *
 * Email sending, PDF/PNG rendering and scheduling run server-side; the UI
 * captures configuration and shows history. No email is actually sent here.
 */
import { LocalStore, latency, nowIso, isoAhead, isoAgo } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'

export type DeliveryFormat = 'pdf' | 'png' | 'csv' | 'excel'
export type DeliveryCadence = 'once' | 'daily' | 'weekly' | 'monthly'

export interface ScheduledDelivery {
  id: string
  dashboardId: string
  dashboardName: string
  recipients: string[]
  format: DeliveryFormat
  cadence: DeliveryCadence
  subject: string
  nextRun: string
  createdAt: string
  active: boolean
  lastStatus?: 'sent' | 'failed' | 'pending'
}

export interface Snapshot {
  id: string
  dashboardId: string
  label: string
  createdAt: string
  pageCount: number
}

const deliveryStore = new LocalStore<ScheduledDelivery[]>('vip.dashboard.deliveries', { scoped: true })
const snapshotStore = new LocalStore<Snapshot[]>('vip.dashboard.snapshots', { scoped: true })

const SEED_DELIVERIES: ScheduledDelivery[] = [
  {
    id: 'del_seed1', dashboardId: 'db_exec', dashboardName: 'Executive Overview',
    recipients: ['leadership@veltrix.com'], format: 'pdf', cadence: 'weekly',
    subject: 'Weekly Executive Overview', nextRun: isoAhead(60 * 24 * 2), createdAt: isoAgo(60 * 24 * 20),
    active: true, lastStatus: 'sent',
  },
  {
    id: 'del_seed2', dashboardId: 'db_revops', dashboardName: 'Revenue Operations',
    recipients: ['revops@veltrix.com', 'finance@veltrix.com'], format: 'excel', cadence: 'daily',
    subject: 'Daily RevOps snapshot', nextRun: isoAhead(60 * 8), createdAt: isoAgo(60 * 24 * 5),
    active: true, lastStatus: 'sent',
  },
]

function nextRunFor(cadence: DeliveryCadence): string {
  const map: Record<DeliveryCadence, number> = { once: 60, daily: 60 * 24, weekly: 60 * 24 * 7, monthly: 60 * 24 * 30 }
  return isoAhead(map[cadence])
}

export type CreateDeliveryInput = Omit<
  ScheduledDelivery,
  'id' | 'createdAt' | 'nextRun' | 'active' | 'lastStatus'
>

export interface DeliveryService {
  list(): Promise<ScheduledDelivery[]>
  create(input: CreateDeliveryInput): Promise<ScheduledDelivery>
  toggle(id: string): Promise<void>
  remove(id: string): Promise<void>
  listSnapshots(dashboardId: string): Promise<Snapshot[]>
  createSnapshot(dashboardId: string, label: string, pageCount: number): Promise<Snapshot>
}

const mockDeliveryService: DeliveryService = {
  async list(): Promise<ScheduledDelivery[]> {
    await latency()
    const stored = deliveryStore.read([])
    return stored.length ? stored : SEED_DELIVERIES
  },

  async create(input: CreateDeliveryInput): Promise<ScheduledDelivery> {
    await latency(200, 420)
    const current = deliveryStore.read(SEED_DELIVERIES.slice())
    const delivery: ScheduledDelivery = {
      ...input,
      id: `del_${Math.random().toString(36).slice(2, 9)}`,
      createdAt: nowIso(),
      nextRun: nextRunFor(input.cadence),
      active: true,
      lastStatus: 'pending',
    }
    deliveryStore.write([delivery, ...current])
    return delivery
  },

  async toggle(id: string): Promise<void> {
    await latency(80, 160)
    const current = deliveryStore.read(SEED_DELIVERIES.slice())
    deliveryStore.write(current.map((d) => (d.id === id ? { ...d, active: !d.active } : d)))
  },

  async remove(id: string): Promise<void> {
    await latency(80, 160)
    const current = deliveryStore.read(SEED_DELIVERIES.slice())
    deliveryStore.write(current.filter((d) => d.id !== id))
  },

  async listSnapshots(dashboardId: string): Promise<Snapshot[]> {
    await latency()
    return snapshotStore.read([]).filter((s) => s.dashboardId === dashboardId)
  },

  async createSnapshot(dashboardId: string, label: string, pageCount: number): Promise<Snapshot> {
    await latency(200, 400)
    const snap: Snapshot = { id: `snap_${Math.random().toString(36).slice(2, 9)}`, dashboardId, label, createdAt: nowIso(), pageCount }
    snapshotStore.write([snap, ...snapshotStore.read([])])
    return snap
  },
}

const apiDeliveryService: DeliveryService = {
  list: () => apiClient.get<ScheduledDelivery[]>('/deliveries'),
  create: (input) => apiClient.post<ScheduledDelivery>('/deliveries', input),
  toggle: (id) => apiClient.post<void>(`/deliveries/${id}/toggle`),
  remove: (id) => apiClient.delete<void>(`/deliveries/${id}`),
  listSnapshots: (dashboardId) =>
    apiClient.get<Snapshot[]>(`/dashboards/${dashboardId}/snapshots`),
  createSnapshot: (dashboardId, label, pageCount) =>
    apiClient.post<Snapshot>(`/dashboards/${dashboardId}/snapshots`, { label, pageCount }),
}

export const deliveryService: DeliveryService = defineService(
  mockDeliveryService,
  () => apiDeliveryService,
)
