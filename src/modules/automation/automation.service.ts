/**
 * Automation module service (mock).
 *
 * Provides automations, their run history and pending approvals for the
 * automation surfaces (list, builder, runs, approvals).
 *
 * INTEGRATION POINT:
 *   GET  /api/v1/automation/automations
 *   GET  /api/v1/automation/automations/:id
 *   GET  /api/v1/automation/runs
 *   GET  /api/v1/automation/runs/:id
 *   GET  /api/v1/automation/approvals
 *   POST /api/v1/automation/automations         (create/update from builder)
 *   POST /api/v1/automation/approvals/:id/decide (approve/reject)
 */
import { latency, isoAgo } from '@/shared/lib/mock'

export type TriggerType =
  | 'schedule'
  | 'pipeline-completed'
  | 'pipeline-failed'
  | 'dataset-refreshed'
  | 'quality-incident'
  | 'connection-failed'
  | 'approval-decision'
  | 'manual'
  | 'webhook'

export type AutomationStatus = 'active' | 'paused' | 'draft'

export interface Automation {
  id: string
  name: string
  trigger: TriggerType
  status: AutomationStatus
  owner: string
  lastRun: string
  runsToday: number
}

export type AutomationRunStatus =
  | 'succeeded'
  | 'failed'
  | 'running'
  | 'waiting-approval'
  | 'dead-letter'

export interface AutomationRunStep {
  name: string
  status: 'succeeded' | 'failed' | 'running' | 'waiting' | 'skipped'
  type: string
}

export interface AutomationRun {
  id: string
  automation: string
  status: AutomationRunStatus
  startedAt: string
  durationMs?: number
  steps: AutomationRunStep[]
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface Approval {
  id: string
  title: string
  requestedBy: string
  requestedAt: string
  status: ApprovalStatus
  context: string
}

/** Trigger presentation metadata used across the automation surfaces. */
export const TRIGGER_META: Record<TriggerType, { label: string; icon: string }> = {
  schedule: { label: 'On schedule', icon: 'calendarClock' },
  'pipeline-completed': { label: 'Pipeline completed', icon: 'workflow' },
  'pipeline-failed': { label: 'Pipeline failed', icon: 'error' },
  'dataset-refreshed': { label: 'Dataset refreshed', icon: 'database' },
  'quality-incident': { label: 'Quality incident', icon: 'gauge' },
  'connection-failed': { label: 'Connection failed', icon: 'plug' },
  'approval-decision': { label: 'Approval decision', icon: 'check' },
  manual: { label: 'Manual', icon: 'play' },
  webhook: { label: 'Webhook', icon: 'webhook' },
}

/** Action palette for the flow builder. */
export const ACTION_CATALOG: { type: string; label: string; icon: string }[] = [
  { type: 'notify', label: 'Send notification', icon: 'bell' },
  { type: 'email', label: 'Send email', icon: 'report' },
  { type: 'report', label: 'Generate report', icon: 'report' },
  { type: 'pipeline', label: 'Trigger pipeline', icon: 'workflow' },
  { type: 'agent', label: 'Run AI agent', icon: 'bot' },
  { type: 'approval', label: 'Create approval', icon: 'check' },
  { type: 'metadata', label: 'Update metadata', icon: 'database' },
  { type: 'api', label: 'Call internal API', icon: 'code' },
  { type: 'webhook', label: 'External webhook', icon: 'webhook' },
]

const AUTOMATIONS: Automation[] = [
  { id: 'au_1', name: 'Alert on revenue pipeline failure', trigger: 'pipeline-failed', status: 'active', owner: 'A. Rahman', lastRun: isoAgo(18), runsToday: 3 },
  { id: 'au_2', name: 'Nightly executive briefing', trigger: 'schedule', status: 'active', owner: 'RevOps', lastRun: isoAgo(480), runsToday: 1 },
  { id: 'au_3', name: 'Quarantine dataset on quality incident', trigger: 'quality-incident', status: 'active', owner: 'Data Quality', lastRun: isoAgo(95), runsToday: 2 },
  { id: 'au_4', name: 'Reconnect on connection failure', trigger: 'connection-failed', status: 'paused', owner: 'Platform', lastRun: isoAgo(2880), runsToday: 0 },
  { id: 'au_5', name: 'Refresh downstream on source update', trigger: 'dataset-refreshed', status: 'active', owner: 'Analytics', lastRun: isoAgo(42), runsToday: 11 },
  { id: 'au_6', name: 'Publish approved reports', trigger: 'approval-decision', status: 'draft', owner: 'Finance', lastRun: isoAgo(4320), runsToday: 0 },
  { id: 'au_7', name: 'Inbound webhook → ingest', trigger: 'webhook', status: 'active', owner: 'Integrations', lastRun: isoAgo(7), runsToday: 46 },
]

const RUNS: AutomationRun[] = [
  {
    id: 'run_1',
    automation: 'Alert on revenue pipeline failure',
    status: 'succeeded',
    startedAt: isoAgo(18),
    durationMs: 4200,
    steps: [
      { name: 'Match trigger', status: 'succeeded', type: 'trigger' },
      { name: 'Evaluate severity condition', status: 'succeeded', type: 'condition' },
      { name: 'Send notification', status: 'succeeded', type: 'notify' },
      { name: 'Send email to on-call', status: 'succeeded', type: 'email' },
    ],
  },
  {
    id: 'run_2',
    automation: 'Nightly executive briefing',
    status: 'running',
    startedAt: isoAgo(3),
    steps: [
      { name: 'Match trigger', status: 'succeeded', type: 'trigger' },
      { name: 'Generate report', status: 'running', type: 'report' },
      { name: 'Send email', status: 'waiting', type: 'email' },
    ],
  },
  {
    id: 'run_3',
    automation: 'Publish approved reports',
    status: 'waiting-approval',
    startedAt: isoAgo(65),
    steps: [
      { name: 'Match trigger', status: 'succeeded', type: 'trigger' },
      { name: 'Create approval', status: 'succeeded', type: 'approval' },
      { name: 'Publish report', status: 'waiting', type: 'api' },
    ],
  },
  {
    id: 'run_4',
    automation: 'Inbound webhook → ingest',
    status: 'dead-letter',
    startedAt: isoAgo(120),
    durationMs: 15200,
    steps: [
      { name: 'Match trigger', status: 'succeeded', type: 'trigger' },
      { name: 'Validate payload', status: 'succeeded', type: 'condition' },
      { name: 'Trigger pipeline', status: 'failed', type: 'pipeline' },
      { name: 'Retry (3/3)', status: 'failed', type: 'pipeline' },
    ],
  },
  {
    id: 'run_5',
    automation: 'Quarantine dataset on quality incident',
    status: 'failed',
    startedAt: isoAgo(95),
    durationMs: 2100,
    steps: [
      { name: 'Match trigger', status: 'succeeded', type: 'trigger' },
      { name: 'Update metadata', status: 'failed', type: 'metadata' },
    ],
  },
]

const APPROVALS: Approval[] = [
  { id: 'ap_1', title: 'Publish "Q3 Board Report" to leadership space', requestedBy: 'Nightly Briefing', requestedAt: isoAgo(65), status: 'pending', context: 'Automation "Publish approved reports" is holding at the publish step pending sign-off.' },
  { id: 'ap_2', title: 'Trigger full reload of fct_orders', requestedBy: 'Refresh downstream', requestedAt: isoAgo(120), status: 'pending', context: 'Source dataset changed schema; a full reload is estimated at 22 minutes and 1.4M rows.' },
  { id: 'ap_3', title: 'Send customer-impact email to 4,200 recipients', requestedBy: 'Incident Response', requestedAt: isoAgo(240), status: 'pending', context: 'Large external send requires human approval per governance policy.' },
  { id: 'ap_4', title: 'Rotate warehouse credentials', requestedBy: 'Platform', requestedAt: isoAgo(1440), status: 'approved', context: 'Approved by M. Almbaidin. Credentials rotated successfully.' },
  { id: 'ap_5', title: 'Delete deprecated dashboard "Legacy KPIs"', requestedBy: 'Cleanup', requestedAt: isoAgo(2880), status: 'rejected', context: 'Rejected — dashboard still referenced by an active subscription.' },
]

export const automationService = {
  async list(): Promise<Automation[]> {
    await latency()
    return AUTOMATIONS
  },

  async get(id: string): Promise<Automation | undefined> {
    await latency()
    return AUTOMATIONS.find((a) => a.id === id)
  },

  async listRuns(): Promise<AutomationRun[]> {
    await latency()
    return RUNS
  },

  async getRun(id: string): Promise<AutomationRun | undefined> {
    await latency()
    return RUNS.find((r) => r.id === id)
  },

  async listApprovals(): Promise<Approval[]> {
    await latency()
    return APPROVALS
  },
}
