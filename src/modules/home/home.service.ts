/**
 * Home aggregation service (mock).
 * INTEGRATION POINT: GET /api/v1/home/summary?workspaceId=...
 */
import { latency, isoAgo } from '@/shared/lib/mock'

export interface HealthMetric { label: string; value: string; delta?: number; tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral'; icon: string; spark: number[] }
export interface RecentResource { id: string; name: string; type: string; icon: string; to: string; when: string }
export interface ActivityEntry { id: string; actor: string; action: string; target: string; when: string; icon: string }
export interface ChecklistItem { id: string; label: string; done: boolean; to: string }

export interface HomeSummary {
  health: HealthMetric[]
  recent: RecentResource[]
  activity: ActivityEntry[]
  checklist: ChecklistItem[]
  pendingApprovals: number
}

export const homeService = {
  async summary(): Promise<HomeSummary> {
    await latency(150, 380)
    return {
      health: [
        { label: 'Connections healthy', value: '11 / 12', delta: 0, tone: 'success', icon: 'plug', spark: [12, 12, 11, 12, 12, 11, 11] },
        { label: 'Pipeline success (24h)', value: '94%', delta: -3, tone: 'warning', icon: 'workflow', spark: [98, 97, 96, 95, 92, 94, 94] },
        { label: 'Datasets fresh', value: '128', delta: 6, tone: 'info', icon: 'database', spark: [110, 114, 118, 120, 124, 126, 128] },
        { label: 'AI usage (month)', value: '68%', delta: 12, tone: 'info', icon: 'sparkles', spark: [40, 46, 51, 55, 60, 64, 68] },
      ],
      recent: [
        { id: 'r1', name: 'Executive Overview', type: 'Dashboard', icon: 'chart', to: '/dashboards/db_exec', when: isoAgo(24) },
        { id: 'r2', name: 'Revenue Nightly ETL', type: 'Pipeline', icon: 'workflow', to: '/pipelines/pl_revenue', when: isoAgo(58) },
        { id: 'r3', name: 'fct_orders', type: 'Dataset', icon: 'database', to: '/datasets/ds_orders', when: isoAgo(120) },
        { id: 'r4', name: 'Sales Analytics', type: 'Semantic Model', icon: 'layers', to: '/semantic/sm_sales', when: isoAgo(200) },
        { id: 'r5', name: 'Q3 Board Report', type: 'Report', icon: 'report', to: '/reports/rp_board', when: isoAgo(300) },
      ],
      activity: [
        { id: 'a1', actor: 'Nightly Scheduler', action: 'ran', target: 'Customer 360 Build', when: isoAgo(12), icon: 'run' },
        { id: 'a2', actor: 'A. Rahman', action: 'published', target: 'Revenue Operations dashboard', when: isoAgo(46), icon: 'chart' },
        { id: 'a3', actor: 'Data Quality', action: 'flagged incident on', target: 'dim_customers', when: isoAgo(90), icon: 'gauge' },
        { id: 'a4', actor: 'You', action: 'created API key', target: 'analytics-service', when: isoAgo(180), icon: 'key' },
        { id: 'a5', actor: 'Automation', action: 'sent alert for', target: 'Revenue Nightly ETL failure', when: isoAgo(240), icon: 'bell' },
      ],
      checklist: [
        { id: 'c1', label: 'Connect your first data source', done: true, to: '/connections/new' },
        { id: 'c2', label: 'Build a pipeline', done: true, to: '/pipelines/new' },
        { id: 'c3', label: 'Create a semantic model', done: true, to: '/semantic' },
        { id: 'c4', label: 'Author a dashboard', done: false, to: '/dashboards/new' },
        { id: 'c5', label: 'Invite a teammate', done: false, to: '/admin/members' },
      ],
      pendingApprovals: 2,
    }
  },
}
