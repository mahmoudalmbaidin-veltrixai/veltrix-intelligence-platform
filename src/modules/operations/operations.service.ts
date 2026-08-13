/**
 * Operations service (mock).
 *
 * Powers the operational surfaces: notifications, activity feed, audit log
 * and usage/quota metering.
 *
 * INTEGRATION POINT
 *   Live backend:
 *     GET /api/v1/notifications                 -> Notification[]
 *     GET /api/v1/activity                       -> ActivityEvent[]
 *     GET /api/v1/audit-events?actor=&result=&from=&to= -> AuditEvent[]
 *     GET /api/v1/usage                          -> UsageMetric[]
 *   Swap `operationsService` for a live adapter; the contract is identical.
 *
 *   NOTE: Audit `before`/`after` payloads are returned pre-redacted by the
 *   backend — secrets/credentials are never included in the diff summaries.
 */
import { latency, isoAgo } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'

export type Severity = 'info' | 'success' | 'warning' | 'danger'

export interface Notification {
  id: string
  severity: Severity
  title: string
  body: string
  category: string
  ts: string
  read: boolean
  /** Optional deep link to the related resource. */
  resource?: { label: string; to: string }
}

export type ActivityDomain = 'pipeline' | 'dataset' | 'dashboard' | 'report' | 'ai' | 'automation' | 'admin' | 'billing'

export interface ActivityEvent {
  id: string
  domain: ActivityDomain
  actor: string
  action: string
  target: string
  ts: string
}

export type AuditResult = 'success' | 'denied' | 'error'

export interface AuditEvent {
  id: string
  actor: string
  action: string
  resource: string
  workspace: string
  org: string
  ip: string
  result: AuditResult
  ts: string
  correlationId: string
  before?: Record<string, unknown>
  after?: Record<string, unknown>
}

export interface UsageMetric {
  label: string
  used: number
  limit: number
  unit: string
}

export interface AuditQuery {
  search?: string
  actor?: string
  result?: AuditResult | 'all'
  from?: string
  to?: string
}

const NOTIFICATIONS: Notification[] = [
  {
    id: 'ntf_01',
    severity: 'danger',
    title: 'Pipeline failed: Billing → Warehouse',
    body: 'Node "Normalize invoices" raised a schema drift error on run #4821.',
    category: 'Pipelines',
    ts: isoAgo(12),
    read: false,
    resource: { label: 'View pipeline', to: '/pipelines/pl_billing_wh' },
  },
  {
    id: 'ntf_02',
    severity: 'warning',
    title: 'Dashboard quota at 82%',
    body: 'Analytics workspace is approaching its dashboard limit for the current plan.',
    category: 'Billing',
    ts: isoAgo(48),
    read: false,
    resource: { label: 'Review usage', to: '/usage' },
  },
  {
    id: 'ntf_03',
    severity: 'success',
    title: 'Report approved: Q2 Revenue Review',
    body: 'Nadia Haddad approved the report. It is now published to Business Viewers.',
    category: 'Reports',
    ts: isoAgo(96),
    read: false,
    resource: { label: 'Open report', to: '/reports/rep_q2_rev' },
  },
  {
    id: 'ntf_04',
    severity: 'info',
    title: 'New extension available',
    body: 'The "Databricks Connector" is now available in the Marketplace for your plan.',
    category: 'Marketplace',
    ts: isoAgo(180),
    read: false,
    resource: { label: 'Open Marketplace', to: '/marketplace' },
  },
  {
    id: 'ntf_05',
    severity: 'warning',
    title: 'API key nearing rate limit',
    body: 'Key "ci-deploy" has used 91% of its hourly request budget.',
    category: 'Developer',
    ts: isoAgo(300),
    read: true,
    resource: { label: 'Manage keys', to: '/developer' },
  },
  {
    id: 'ntf_06',
    severity: 'info',
    title: 'Scheduled maintenance',
    body: 'Platform maintenance window on Sat 02:00–03:00 UTC. No downtime expected.',
    category: 'System',
    ts: isoAgo(720),
    read: true,
  },
  {
    id: 'ntf_07',
    severity: 'success',
    title: 'Dataset certified',
    body: '"dim_customer" was certified by the Data Platform team.',
    category: 'Datasets',
    ts: isoAgo(900),
    read: true,
    resource: { label: 'View dataset', to: '/datasets/dim_customer' },
  },
  {
    id: 'ntf_08',
    severity: 'danger',
    title: 'Automation disabled',
    body: 'Automation "Nightly refresh" was auto-disabled after 3 consecutive failures.',
    category: 'Automation',
    ts: isoAgo(1440),
    read: true,
    resource: { label: 'Open automation', to: '/automations/au_nightly' },
  },
]

const ACTIVITY: ActivityEvent[] = [
  {
    id: 'act_01',
    domain: 'pipeline',
    actor: 'Mahmoud Almbaidin',
    action: 'ran',
    target: 'Billing → Warehouse',
    ts: isoAgo(8),
  },
  {
    id: 'act_02',
    domain: 'dashboard',
    actor: 'Lena Fischer',
    action: 'published',
    target: 'Executive Overview',
    ts: isoAgo(26),
  },
  {
    id: 'act_03',
    domain: 'ai',
    actor: 'Omar Khalid',
    action: 'created agent',
    target: 'Revenue Anomaly Watcher',
    ts: isoAgo(52),
  },
  {
    id: 'act_04',
    domain: 'report',
    actor: 'Nadia Haddad',
    action: 'approved',
    target: 'Q2 Revenue Review',
    ts: isoAgo(96),
  },
  {
    id: 'act_05',
    domain: 'dataset',
    actor: 'Data Platform',
    action: 'certified',
    target: 'dim_customer',
    ts: isoAgo(140),
  },
  {
    id: 'act_06',
    domain: 'automation',
    actor: 'System',
    action: 'disabled',
    target: 'Nightly refresh',
    ts: isoAgo(220),
  },
  {
    id: 'act_07',
    domain: 'admin',
    actor: 'Mahmoud Almbaidin',
    action: 'invited',
    target: 'sara.mansour@veltrix.com',
    ts: isoAgo(300),
  },
  {
    id: 'act_08',
    domain: 'billing',
    actor: 'Nadia Haddad',
    action: 'updated plan',
    target: 'Enterprise (annual)',
    ts: isoAgo(1440),
  },
  {
    id: 'act_09',
    domain: 'pipeline',
    actor: 'Omar Khalid',
    action: 'published',
    target: 'Marketing Events ETL',
    ts: isoAgo(1500),
  },
  {
    id: 'act_10',
    domain: 'dashboard',
    actor: 'Lena Fischer',
    action: 'shared',
    target: 'Churn Cohorts',
    ts: isoAgo(1600),
  },
  {
    id: 'act_11',
    domain: 'dataset',
    actor: 'Data Platform',
    action: 'created',
    target: 'fct_orders',
    ts: isoAgo(2900),
  },
  {
    id: 'act_12',
    domain: 'ai',
    actor: 'Mahmoud Almbaidin',
    action: 'queried',
    target: 'Why did EU revenue drop?',
    ts: isoAgo(4400),
  },
]

const AUDIT: AuditEvent[] = [
  {
    id: 'aud_01',
    actor: 'mahmoud.almbaidin@veltrix.com',
    action: 'connection.create',
    resource: 'conn_pg_core',
    workspace: 'Platform',
    org: 'Current organization',
    ip: '84.23.11.4',
    result: 'success',
    ts: isoAgo(14),
    correlationId: 'corr_9f2a17c4',
    before: undefined,
    after: { name: 'Core Warehouse (Postgres)', host: 'wh-core.veltrix.internal:5432', secret: '••••redacted••••' },
  },
  {
    id: 'aud_02',
    actor: 'omar.khalid@veltrix.com',
    action: 'pipeline.run',
    resource: 'pl_billing_wh',
    workspace: 'Revenue Ops',
    org: 'Current organization',
    ip: '84.23.11.9',
    result: 'error',
    ts: isoAgo(24),
    correlationId: 'corr_a1b2c3d4',
  },
  {
    id: 'aud_03',
    actor: 'lena.fischer@veltrix.com',
    action: 'dashboard.publish',
    resource: 'dsh_exec_overview',
    workspace: 'Analytics',
    org: 'Current organization',
    ip: '52.19.44.201',
    result: 'success',
    ts: isoAgo(40),
    correlationId: 'corr_55aa66bb',
    before: { visibility: 'private' },
    after: { visibility: 'workspace' },
  },
  {
    id: 'aud_04',
    actor: 'guest.viewer@northwind.com',
    action: 'report.export',
    resource: 'rep_q2_rev',
    workspace: 'Sandbox',
    org: 'Current organization',
    ip: '198.51.100.7',
    result: 'denied',
    ts: isoAgo(58),
    correlationId: 'corr_deadbeef',
  },
  {
    id: 'aud_05',
    actor: 'nadia.haddad@veltrix.com',
    action: 'billing.plan.update',
    resource: 'current-organization',
    workspace: '—',
    org: 'Current organization',
    ip: '84.23.11.2',
    result: 'success',
    ts: isoAgo(120),
    correlationId: 'corr_7788aabb',
    before: { plan: 'business' },
    after: { plan: 'enterprise' },
  },
  {
    id: 'aud_06',
    actor: 'mahmoud.almbaidin@veltrix.com',
    action: 'member.invite',
    resource: 'sara.mansour@veltrix.com',
    workspace: '—',
    org: 'Current organization',
    ip: '84.23.11.4',
    result: 'success',
    ts: isoAgo(300),
    correlationId: 'corr_1122ccdd',
    after: { role: 'analyst', status: 'invited' },
  },
  {
    id: 'aud_07',
    actor: 'ci-deploy (api key)',
    action: 'apikey.use',
    resource: 'key_ci_deploy',
    workspace: 'Platform',
    org: 'Current organization',
    ip: '3.120.55.8',
    result: 'success',
    ts: isoAgo(320),
    correlationId: 'corr_ff00ee11',
  },
  {
    id: 'aud_08',
    actor: 'omar.khalid@veltrix.com',
    action: 'featureflag.toggle',
    resource: 'ai-agents-beta',
    workspace: '—',
    org: 'Current organization',
    ip: '84.23.11.9',
    result: 'success',
    ts: isoAgo(420),
    correlationId: 'corr_ab12cd34',
    before: { enabled: false },
    after: { enabled: true },
  },
  {
    id: 'aud_09',
    actor: 'unknown',
    action: 'auth.login',
    resource: 'usr_veltrix_01',
    workspace: '—',
    org: 'Current organization',
    ip: '45.146.26.19',
    result: 'denied',
    ts: isoAgo(520),
    correlationId: 'corr_bad10gin',
  },
  {
    id: 'aud_10',
    actor: 'nadia.haddad@veltrix.com',
    action: 'governance.policy.update',
    resource: 'retention.audit',
    workspace: '—',
    org: 'Current organization',
    ip: '84.23.11.2',
    result: 'success',
    ts: isoAgo(700),
    correlationId: 'corr_gov00001',
    before: { value: '90d' },
    after: { value: '365d' },
  },
  {
    id: 'aud_11',
    actor: 'lena.fischer@veltrix.com',
    action: 'dataset.certify',
    resource: 'dim_customer',
    workspace: 'Analytics',
    org: 'Current organization',
    ip: '52.19.44.201',
    result: 'success',
    ts: isoAgo(900),
    correlationId: 'corr_cert1234',
  },
  {
    id: 'aud_12',
    actor: 'mahmoud.almbaidin@veltrix.com',
    action: 'workspace.archive',
    resource: 'ws_legacy',
    workspace: 'Legacy',
    org: 'Current organization',
    ip: '84.23.11.4',
    result: 'success',
    ts: isoAgo(1300),
    correlationId: 'corr_arch9999',
    before: { archived: false },
    after: { archived: true },
  },
  {
    id: 'aud_13',
    actor: 'system',
    action: 'automation.autodisable',
    resource: 'au_nightly',
    workspace: 'Revenue Ops',
    org: 'Current organization',
    ip: '10.0.0.1',
    result: 'error',
    ts: isoAgo(1440),
    correlationId: 'corr_auto0003',
  },
  {
    id: 'aud_14',
    actor: 'sara.mansour@veltrix.com',
    action: 'apikey.create',
    resource: 'key_reporting',
    workspace: 'Analytics',
    org: 'Current organization',
    ip: '84.23.11.31',
    result: 'success',
    ts: isoAgo(1600),
    correlationId: 'corr_key55667',
    after: { name: 'reporting-readonly', scopes: 'read:datasets, read:dashboards', secret: '••••redacted••••' },
  },
  {
    id: 'aud_15',
    actor: 'omar.khalid@veltrix.com',
    action: 'extension.install',
    resource: 'ext_dbt_metrics',
    workspace: 'Platform',
    org: 'Current organization',
    ip: '84.23.11.9',
    result: 'success',
    ts: isoAgo(2100),
    correlationId: 'corr_ext11223',
  },
]

const USAGE: UsageMetric[] = [
  { label: 'Pipeline runs', used: 8420, limit: 10000, unit: 'runs / mo' },
  { label: 'Rows processed', used: 742_000_000, limit: 1_000_000_000, unit: 'rows / mo' },
  { label: 'AI assistant queries', used: 1880, limit: 2000, unit: 'queries / mo' },
  { label: 'API requests', used: 512_000, limit: 500_000, unit: 'requests / mo' },
  { label: 'Storage', used: 340, limit: 500, unit: 'GB' },
  { label: 'Seats', used: 46, limit: 60, unit: 'members' },
]

function matches(a: AuditEvent, q?: AuditQuery): boolean {
  if (!q) return true
  if (q.result && q.result !== 'all' && a.result !== q.result) return false
  if (q.actor && a.actor !== q.actor) return false
  if (q.search) {
    const s = q.search.toLowerCase()
    const hit =
      a.actor.toLowerCase().includes(s) ||
      a.action.toLowerCase().includes(s) ||
      a.resource.toLowerCase().includes(s) ||
      a.correlationId.toLowerCase().includes(s)
    if (!hit) return false
  }
  if (q.from && new Date(a.ts).getTime() < new Date(q.from).getTime()) return false
  if (q.to && new Date(a.ts).getTime() > new Date(q.to).getTime()) return false
  return true
}

/**
 * Domain service contract. Views/composables depend on this interface via the
 * `operationsService` factory export — never on a concrete implementation.
 */
export interface OperationsService {
  listNotifications(): Promise<Notification[]>
  /** Authoritative unread count for the signed-in user (badge source of truth). */
  unreadNotificationCount(): Promise<number>
  /** Persist a single notification as read; returns the new unread count. */
  markNotificationRead(id: string): Promise<number>
  /** Remove a single notification's read marker; returns the new unread count. */
  markNotificationUnread(id: string): Promise<number>
  /** Persist all notifications as read; returns the new unread count (0). */
  markAllNotificationsRead(): Promise<number>
  listActivity(): Promise<ActivityEvent[]>
  listAudit(params?: AuditQuery): Promise<AuditEvent[]>
  listUsage(): Promise<UsageMetric[]>
}

const mockOperationsService: OperationsService = {
  async listNotifications(): Promise<Notification[]> {
    await latency()
    return NOTIFICATIONS.map((n) => ({ ...n }))
  },

  async unreadNotificationCount(): Promise<number> {
    await latency()
    return NOTIFICATIONS.filter((n) => !n.read).length
  },

  async markNotificationRead(id: string): Promise<number> {
    await latency()
    const target = NOTIFICATIONS.find((n) => n.id === id)
    if (target) target.read = true
    return NOTIFICATIONS.filter((n) => !n.read).length
  },

  async markNotificationUnread(id: string): Promise<number> {
    await latency()
    const target = NOTIFICATIONS.find((n) => n.id === id)
    if (target) target.read = false
    return NOTIFICATIONS.filter((n) => !n.read).length
  },

  async markAllNotificationsRead(): Promise<number> {
    await latency()
    NOTIFICATIONS.forEach((n) => {
      n.read = true
    })
    return 0
  },

  async listActivity(): Promise<ActivityEvent[]> {
    await latency()
    return ACTIVITY.map((a) => ({ ...a }))
  },

  async listAudit(params?: AuditQuery): Promise<AuditEvent[]> {
    await latency()
    return AUDIT.filter((a) => matches(a, params)).map((a) => ({ ...a }))
  },

  async listUsage(): Promise<UsageMetric[]> {
    await latency()
    return USAGE.map((u) => ({ ...u }))
  },
}

/**
 * Live adapter — routes through the centralized API client. Endpoint paths
 * reflect the expected backend contract (see docs/BACKEND_INTEGRATION.md).
 */
const apiOperationsService: OperationsService = {
  listNotifications: () => apiClient.get<Notification[]>('/notifications'),
  unreadNotificationCount: () => apiClient.get<{ count: number }>('/notifications/unread-count').then((r) => r.count),
  markNotificationRead: (id) =>
    apiClient.post<{ count: number }>(`/notifications/${encodeURIComponent(id)}/read`).then((r) => r.count),
  markNotificationUnread: (id) =>
    apiClient.delete<{ count: number }>(`/notifications/${encodeURIComponent(id)}/read`).then((r) => r.count),
  markAllNotificationsRead: () => apiClient.post<{ count: number }>('/notifications/read-all').then((r) => r.count),
  listActivity: () => apiClient.get<ActivityEvent[]>('/activity'),
  listAudit: (params) =>
    // Canonical audit route is /audit-events (the Audit Center uses it via
    // governance/auditService). This adapter is retained for API completeness.
    apiClient.get<AuditEvent[]>('/audit-events', {
      query: {
        search: params?.search,
        actor: params?.actor,
        result: params?.result,
        from: params?.from,
        to: params?.to,
      },
    }),
  listUsage: () => apiClient.get<UsageMetric[]>('/usage'),
}

/** Selected by VITE_API_MODE. Views import this, not a concrete class. */
export const operationsService: OperationsService = defineService(mockOperationsService, () => apiOperationsService)
