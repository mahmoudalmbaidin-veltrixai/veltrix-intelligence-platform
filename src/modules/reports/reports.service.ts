/**
 * Reports service (mock).
 *
 * Backs the report list, the paginated report builder, scheduled deliveries
 * and the export history. Report lifecycle follows a review workflow:
 *   draft -> in-review -> approved | rejected -> published
 *
 * INTEGRATION POINT
 *   GET  /api/v1/reports                    -> Report[]
 *   GET  /api/v1/reports/:id                -> Report
 *   GET  /api/v1/reports/templates          -> ReportTemplate[]
 *   GET  /api/v1/reports/deliveries         -> Delivery[]
 *   GET  /api/v1/reports/exports            -> ExportJob[]
 *   POST /api/v1/reports/deliveries         -> Delivery (create)
 * Swap the mock bodies for a live adapter; the return contracts are identical.
 */
import { latency, isoAgo, isoAhead } from '@/shared/lib/mock'
import { apiClient } from '@/shared/lib/apiClient'
import { defineService } from '@/shared/services/serviceFactory'

export type ReportStatus = 'draft' | 'in-review' | 'approved' | 'rejected' | 'published'

export interface Report {
  id: string
  name: string
  description: string
  status: ReportStatus
  owner: string
  updatedAt: string
  version: string
  reviewers: string[]
}

export interface ReportTemplate {
  id: string
  name: string
  description: string
  sections: number
}

export type DeliverySchedule = 'daily' | 'weekly' | 'monthly'
export type DeliveryFormat = 'pdf' | 'excel' | 'csv'
export type DeliveryStatus = 'sent' | 'failed' | 'pending'

export interface Delivery {
  id: string
  report: string
  schedule: DeliverySchedule
  format: DeliveryFormat
  recipients: number
  nextRun: string
  lastStatus: DeliveryStatus
}

export type ExportStatus = 'queued' | 'rendering' | 'ready' | 'expired'

export interface ExportJob {
  id: string
  report: string
  format: DeliveryFormat
  status: ExportStatus
  createdAt: string
}

const REPORTS: Report[] = [
  { id: 'rp_board', name: 'Q3 Board Report', description: 'Quarterly performance pack for the board of directors.', status: 'in-review', owner: 'A. Rahman', updatedAt: isoAgo(35), version: 'v4.2', reviewers: ['Board Office', 'Finance', 'Legal'] },
  { id: 'rp_revops', name: 'Revenue Operations Review', description: 'Weekly pipeline, bookings and forecast attainment.', status: 'published', owner: 'Revenue Ops', updatedAt: isoAgo(180), version: 'v12.0', reviewers: ['CRO'] },
  { id: 'rp_finance', name: 'Monthly Financial Statements', description: 'P&L, balance sheet and cash flow with commentary.', status: 'approved', owner: 'Finance', updatedAt: isoAgo(60 * 20), version: 'v8.1', reviewers: ['Controller', 'CFO'] },
  { id: 'rp_marketing', name: 'Marketing Attribution', description: 'Channel spend, CAC and campaign ROI breakdown.', status: 'draft', owner: 'Growth', updatedAt: isoAgo(60 * 5), version: 'v0.3', reviewers: [] },
  { id: 'rp_ops', name: 'Platform Reliability Report', description: 'SLA attainment, incidents and error budgets.', status: 'published', owner: 'Platform', updatedAt: isoAgo(60 * 40), version: 'v6.4', reviewers: ['VP Eng'] },
  { id: 'rp_exec', name: 'Executive Weekly', description: 'One-page executive summary across the business.', status: 'rejected', owner: 'Chief of Staff', updatedAt: isoAgo(60 * 8), version: 'v2.7', reviewers: ['CEO', 'CFO'] },
  { id: 'rp_supply', name: 'Supply Chain Scorecard', description: 'Inventory turns, fill rate and logistics cost.', status: 'in-review', owner: 'Supply Chain', updatedAt: isoAgo(60 * 12), version: 'v3.0', reviewers: ['COO'] },
]

const TEMPLATES: ReportTemplate[] = [
  { id: 'tpl_board', name: 'Board Pack', description: 'Cover, executive summary, financials and appendix.', sections: 8 },
  { id: 'tpl_kpi', name: 'KPI Scorecard', description: 'Single-page grid of headline metrics with trend.', sections: 3 },
  { id: 'tpl_financial', name: 'Financial Statements', description: 'P&L, balance sheet and cash flow layouts.', sections: 6 },
  { id: 'tpl_ops', name: 'Operations Review', description: 'Reliability, incidents and error-budget sections.', sections: 5 },
  { id: 'tpl_sales', name: 'Sales Review', description: 'Pipeline, bookings and forecast attainment.', sections: 4 },
  { id: 'tpl_blank', name: 'Blank Document', description: 'Start from an empty page with no preset blocks.', sections: 0 },
]

const DELIVERIES: Delivery[] = [
  { id: 'dl_1', report: 'Revenue Operations Review', schedule: 'weekly', format: 'pdf', recipients: 14, nextRun: isoAhead(60 * 20), lastStatus: 'sent' },
  { id: 'dl_2', report: 'Monthly Financial Statements', schedule: 'monthly', format: 'excel', recipients: 6, nextRun: isoAhead(60 * 24 * 9), lastStatus: 'sent' },
  { id: 'dl_3', report: 'Platform Reliability Report', schedule: 'weekly', format: 'pdf', recipients: 22, nextRun: isoAhead(60 * 46), lastStatus: 'failed' },
  { id: 'dl_4', report: 'Executive Weekly', schedule: 'weekly', format: 'pdf', recipients: 5, nextRun: isoAhead(60 * 8), lastStatus: 'pending' },
  { id: 'dl_5', report: 'Marketing Attribution', schedule: 'daily', format: 'csv', recipients: 3, nextRun: isoAhead(60 * 3), lastStatus: 'sent' },
]

const EXPORTS: ExportJob[] = [
  { id: 'ex_1', report: 'Q3 Board Report', format: 'pdf', status: 'ready', createdAt: isoAgo(40) },
  { id: 'ex_2', report: 'Revenue Operations Review', format: 'excel', status: 'ready', createdAt: isoAgo(120) },
  { id: 'ex_3', report: 'Platform Reliability Report', format: 'pdf', status: 'rendering', createdAt: isoAgo(4) },
  { id: 'ex_4', report: 'Marketing Attribution', format: 'csv', status: 'queued', createdAt: isoAgo(1) },
  { id: 'ex_5', report: 'Monthly Financial Statements', format: 'pdf', status: 'expired', createdAt: isoAgo(60 * 24 * 8) },
]

/**
 * Domain service contract. Views/composables depend on this interface via the
 * `reportService` factory export — never on a concrete implementation.
 */
export interface ReportService {
  list(): Promise<Report[]>
  get(id: string): Promise<Report | undefined>
  listTemplates(): Promise<ReportTemplate[]>
  listDeliveries(): Promise<Delivery[]>
  listExports(): Promise<ExportJob[]>
  createDelivery(input: Omit<Delivery, 'id'>): Promise<Delivery>
}

const mockReportService: ReportService = {
  async list(): Promise<Report[]> {
    await latency(140, 320)
    return REPORTS
  },
  async get(id: string): Promise<Report | undefined> {
    await latency(120, 260)
    return REPORTS.find((r) => r.id === id)
  },
  async listTemplates(): Promise<ReportTemplate[]> {
    await latency(120, 280)
    return TEMPLATES
  },
  async listDeliveries(): Promise<Delivery[]> {
    await latency(140, 320)
    return DELIVERIES
  },
  async listExports(): Promise<ExportJob[]> {
    await latency(120, 280)
    return EXPORTS
  },
  /** Persist a scheduled delivery (mock — pushes into the in-memory seed). */
  async createDelivery(input: Omit<Delivery, 'id'>): Promise<Delivery> {
    await latency(200, 420)
    const delivery: Delivery = { ...input, id: `dl_${Math.random().toString(36).slice(2, 9)}` }
    DELIVERIES.unshift(delivery)
    return delivery
  },
}

/**
 * Live adapter — routes through the centralized API client. Endpoint paths
 * reflect the expected backend contract (see BACKEND_INTEGRATION.md).
 */
const apiReportService: ReportService = {
  list: () => apiClient.get<Report[]>('/reports'),
  get: (id) => apiClient.get<Report | undefined>(`/reports/${id}`),
  listTemplates: () => apiClient.get<ReportTemplate[]>('/reports/templates'),
  listDeliveries: () => apiClient.get<Delivery[]>('/reports/deliveries'),
  listExports: () => apiClient.get<ExportJob[]>('/reports/exports'),
  createDelivery: (input) => apiClient.post<Delivery>('/reports/deliveries', input),
}

/** Selected by VITE_API_MODE. Views import this, not a concrete class. */
export const reportService: ReportService = defineService(mockReportService, () => apiReportService)
