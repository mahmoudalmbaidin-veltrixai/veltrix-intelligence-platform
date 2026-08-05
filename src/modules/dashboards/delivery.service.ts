/** Live B6.5 dashboard export and delivery API adapter. */
import { apiClient } from '@/shared/lib/apiClient'
import { downloadBlob } from '@/shared/lib/download'

const API = '/api/v1'

export type ExportFormat = 'pdf' | 'png' | 'json' | 'csv'
export type DeliveryFormat = ExportFormat
export type DeliveryCadence = 'one_time' | 'daily' | 'weekly' | 'monthly' | 'cron'
export type ExportStatus = 'queued' | 'rendering' | 'completed' | 'failed' | 'cancelled' | 'expired'

export interface DashboardExport {
  id: string
  dashboard_id: string
  dashboard_version_id: string
  format: ExportFormat
  status: ExportStatus
  progress: number
  attempts: number
  max_attempts: number
  cancellation_requested: boolean
  artifact_content_type: string | null
  artifact_size_bytes: number | null
  safe_error_code: string | null
  safe_error_message: string | null
  row_version: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  expires_at: string | null
}

export interface ScheduledDelivery {
  id: string
  dashboard_id: string
  dashboard_version_id: string
  name: string
  recipients: string[]
  cc: string[]
  bcc: string[]
  subject: string
  format: DeliveryFormat
  filters: Record<string, unknown>
  schedule_type: DeliveryCadence
  schedule_expression: string | null
  timezone: string
  include_dashboard_link: boolean
  enabled: boolean
  status: string
  retry_count: number
  max_retries: number
  row_version: number
  created_at: string
  updated_at: string
  last_run_at: string | null
  next_run_at: string | null
}

export interface DeliveryRun {
  id: string
  schedule_id: string
  export_id: string | null
  status: string
  attempt: number
  safe_error_code: string | null
  safe_error_message: string | null
  created_at: string
  sent_at: string | null
  completed_at: string | null
}

export interface CreateDeliveryInput {
  name: string
  recipients: string[]
  cc?: string[]
  bcc?: string[]
  subject: string
  format: DeliveryFormat
  filters?: Record<string, unknown>
  schedule_type: DeliveryCadence
  schedule_expression?: string | null
  run_at?: string | null
  timezone: string
  include_dashboard_link?: boolean
  enabled?: boolean
  max_retries?: number
}

export interface EmailPreview {
  subject: string
  html: string
  recipients: number
  attachments: string[]
}

export const deliveryService = {
  list: (dashboardId?: string) =>
    apiClient.get<ScheduledDelivery[]>(
      dashboardId ? `${API}/dashboards/${dashboardId}/deliveries` : `${API}/dashboard-deliveries`,
    ),
  create: (dashboardId: string, input: CreateDeliveryInput) =>
    apiClient.post<ScheduledDelivery>(`${API}/dashboards/${dashboardId}/deliveries`, input),
  update: (delivery: ScheduledDelivery, input: CreateDeliveryInput) =>
    apiClient.put<ScheduledDelivery>(`${API}/dashboard-deliveries/${delivery.id}`, {
      ...input,
      expected_version: delivery.row_version,
    }),
  toggle: (delivery: ScheduledDelivery) =>
    apiClient.put<ScheduledDelivery>(`${API}/dashboard-deliveries/${delivery.id}`, {
      name: delivery.name,
      recipients: delivery.recipients,
      cc: delivery.cc,
      bcc: delivery.bcc,
      subject: delivery.subject,
      format: delivery.format,
      filters: delivery.filters,
      schedule_type: delivery.schedule_type,
      schedule_expression: delivery.schedule_expression,
      run_at: delivery.schedule_type === 'one_time' ? delivery.next_run_at : null,
      timezone: delivery.timezone,
      include_dashboard_link: delivery.include_dashboard_link,
      enabled: !delivery.enabled,
      max_retries: delivery.max_retries,
      expected_version: delivery.row_version,
    }),
  remove: (delivery: ScheduledDelivery) =>
    apiClient.delete<void>(`${API}/dashboard-deliveries/${delivery.id}`, {
      query: { expected_version: delivery.row_version },
    }),
  history: (id: string) => apiClient.get<DeliveryRun[]>(`${API}/dashboard-deliveries/${id}/history`),
  test: (id: string) => apiClient.post<DeliveryRun>(`${API}/dashboard-deliveries/${id}/test`),
  preview: (
    dashboardId: string,
    input: { recipients: string[]; cc?: string[]; bcc?: string[]; subject: string; include_dashboard_link?: boolean },
  ) => apiClient.post<EmailPreview>(`${API}/dashboards/${dashboardId}/deliveries/preview-email`, input),
  exports: (dashboardId: string) => apiClient.get<DashboardExport[]>(`${API}/dashboards/${dashboardId}/exports`),
  createExport: (dashboardId: string, format: ExportFormat, filters: Record<string, unknown> = {}) =>
    apiClient.post<DashboardExport>(`${API}/dashboards/${dashboardId}/exports`, {
      format,
      filters,
      locale: navigator.language || 'en-US',
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    }),
  exportStatus: (id: string) => apiClient.get<DashboardExport>(`${API}/dashboard-exports/${id}`),
  cancelExport: (job: DashboardExport) =>
    apiClient.post<DashboardExport>(`${API}/dashboard-exports/${job.id}/cancel`, {
      expected_version: job.row_version,
    }),
  retryExport: (job: DashboardExport) =>
    apiClient.post<DashboardExport>(`${API}/dashboard-exports/${job.id}/retry`, { expected_version: job.row_version }),
  async downloadExport(job: DashboardExport): Promise<void> {
    const signed = await apiClient.post<{ url: string }>(`${API}/dashboard-exports/${job.id}/download-token`)
    const artifact = await apiClient.downloadWithMetadata(signed.url)
    downloadBlob(artifact.fileName, artifact.blob)
  },
}
