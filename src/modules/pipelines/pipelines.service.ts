/** Live B7 pipeline REST adapter. No production-path seeds or local persistence. */
import { apiClient } from '@/shared/lib/apiClient'
import type {
  ArtifactDownloadLink,
  Pipeline,
  PipelineAccess,
  PipelineAccessLevel,
  PipelineArtifact,
  PipelineListItem,
  PipelineNode,
  PipelineRun,
  RunLogEntry,
  RunNodeState,
  SchemaColumn,
  ValidationReport,
} from '@/shared/types/pipeline'
import type { DataType } from '@/shared/types/semantic'

/** Map a source database/physical type string onto the editor's DataType. */
function toDataType(value: string): DataType {
  const type = value.toLowerCase()
  if (type.includes('timestamp')) return 'datetime'
  if (type === 'date') return 'date'
  if (type.includes('bool')) return 'boolean'
  if (type.includes('int')) return 'integer'
  if (/(numeric|decimal|float|double|real)/.test(type)) return 'number'
  return 'string'
}

/**
 * Rebuild a source node's output schema from its persisted `schema_snapshot`
 * (a bounded `[{name,type,nullable}]` list written when the source was
 * configured). Restoring this on load is what lets the downstream Select,
 * Rename, and Formula editors show upstream columns without the user having to
 * perturb the graph. Returns undefined when no valid snapshot is present so the
 * caller can surface a clear "schema unavailable" state instead of inventing
 * columns.
 */
function sourceSchemaFromConfig(config: Record<string, unknown>): SchemaColumn[] | undefined {
  const snapshot = config.schema_snapshot
  if (!Array.isArray(snapshot) || snapshot.length === 0) return undefined
  const columns: SchemaColumn[] = []
  for (const entry of snapshot) {
    if (entry && typeof entry === 'object' && typeof (entry as { name?: unknown }).name === 'string') {
      const field = entry as { name: string; type?: unknown }
      columns.push({
        name: field.name,
        dataType: toDataType(typeof field.type === 'string' ? field.type : 'string'),
      })
    }
  }
  return columns.length > 0 ? columns : undefined
}

interface SummaryDto {
  id: string
  name: string
  description: string
  status: 'draft' | 'published'
  tags: string[]
  row_version: number
  published_version: number | null
  node_count: number
  last_run_at: string | null
  last_run_status: string | null
  updated_at: string
}
interface NodeDto {
  id?: string | null
  key: string
  type: PipelineNode['kind']
  title: string
  x: number
  y: number
  config: Record<string, unknown>
}
interface EdgeDto {
  id?: string | null
  key: string
  source: string
  target: string
  source_port?: string | null
  target_port?: string | null
}
interface AccessDto {
  level: string | null
  allowed_levels: string[]
  can_view: boolean
  can_run: boolean
  can_edit: boolean
  can_manage: boolean
  source: string
  reason: string
}
interface EditorDto {
  pipeline: SummaryDto
  canvas: Record<string, unknown>
  nodes: NodeDto[]
  edges: EdgeDto[]
  access?: AccessDto | null
}
interface RunDto {
  id: string
  pipeline_id: string
  status: PipelineRun['status']
  progress: number
  trigger: PipelineRun['trigger']
  correlation_id: string
  current_attempt: number
  rows_processed: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  safe_error_message: string | null
  nodes?: Array<{
    node_key: string
    status: RunNodeState['status']
    rows_out: number
    started_at: string | null
    completed_at: string | null
  }>
  logs?: Array<{
    created_at: string
    level: 'info' | 'warning' | 'error'
    node_key: string | null
    message: string
  }>
}

interface ArtifactDto {
  id: string
  node_key: string
  content_type: string
  size_bytes: number
  sha256: string
  expires_at: string
  created_at: string
}

const nodeId = (node: NodeDto) => node.key
function mapAccess(dto: AccessDto | null | undefined): PipelineAccess | undefined {
  if (!dto) return undefined
  return {
    level: (dto.level as PipelineAccessLevel | null) ?? null,
    allowedLevels: (dto.allowed_levels ?? []) as PipelineAccessLevel[],
    canView: dto.can_view,
    canRun: dto.can_run,
    canEdit: dto.can_edit,
    canManage: dto.can_manage,
    source: dto.source,
    reason: dto.reason,
  }
}
function mapEditor(dto: EditorDto): Pipeline {
  return {
    id: dto.pipeline.id,
    name: dto.pipeline.name,
    description: dto.pipeline.description,
    status: dto.pipeline.status,
    version: dto.pipeline.published_version ?? 0,
    rowVersion: dto.pipeline.row_version,
    owner: 'You',
    tags: dto.pipeline.tags,
    nodes: dto.nodes.map((node) => {
      const mapped: PipelineNode = {
        id: nodeId(node),
        kind: node.type,
        title: node.title,
        x: node.x,
        y: node.y,
        config: node.config,
      }
      // Restore the persisted upstream schema for source nodes so the loaded
      // graph can propagate columns to downstream editors immediately.
      if (node.type === 'source-dataset') {
        const restored = sourceSchemaFromConfig(node.config)
        if (restored) mapped.outputSchema = restored
      }
      return mapped
    }),
    edges: dto.edges.map((edge) => ({
      id: edge.key,
      sourceNode: edge.source,
      targetNode: edge.target,
      sourcePort: edge.source_port ?? 'out',
      targetPort: edge.target_port ?? 'in',
    })),
    canvas: {
      x: typeof dto.canvas.x === 'number' ? dto.canvas.x : 40,
      y: typeof dto.canvas.y === 'number' ? dto.canvas.y : 40,
      scale: typeof dto.canvas.scale === 'number' ? dto.canvas.scale : 1,
      snapGrid: typeof dto.canvas.snapGrid === 'boolean' ? dto.canvas.snapGrid : true,
      initialized: typeof dto.canvas.initialized === 'boolean' ? dto.canvas.initialized : false,
    },
    updatedAt: dto.pipeline.updated_at,
    lastRunAt: dto.pipeline.last_run_at ?? undefined,
    lastRunStatus: (dto.pipeline.last_run_status as Pipeline['lastRunStatus']) ?? undefined,
    access: mapAccess(dto.access),
  }
}
function mapSummary(dto: SummaryDto): PipelineListItem {
  return {
    id: dto.id,
    name: dto.name,
    status: dto.status,
    owner: 'You',
    tags: dto.tags,
    version: dto.published_version ?? 0,
    rowVersion: dto.row_version,
    updatedAt: dto.updated_at,
    lastRunAt: dto.last_run_at ?? undefined,
    lastRunStatus: (dto.last_run_status as PipelineListItem['lastRunStatus']) ?? undefined,
    nodeCount: dto.node_count,
  }
}
function graphBody(pipeline: Pipeline) {
  return {
    name: pipeline.name,
    description: pipeline.description,
    tags: pipeline.tags,
    canvas: pipeline.canvas,
    nodes: pipeline.nodes.map((node) => ({
      key: node.id,
      type: node.kind,
      title: node.title,
      x: node.x,
      y: node.y,
      config: node.config,
    })),
    edges: pipeline.edges.map((edge) => ({
      key: edge.id,
      source: edge.sourceNode,
      target: edge.targetNode,
      source_port: edge.sourcePort,
      target_port: edge.targetPort,
    })),
  }
}
function saveBody(pipeline: Pipeline) {
  return { ...graphBody(pipeline), expected_version: pipeline.rowVersion }
}
function mapRun(dto: RunDto): PipelineRun {
  const states: RunNodeState[] = (dto.nodes ?? []).map((node) => ({
    nodeId: node.node_key,
    status: node.status,
    rows: node.rows_out,
    durationMs:
      node.started_at && node.completed_at
        ? new Date(node.completed_at).getTime() - new Date(node.started_at).getTime()
        : undefined,
  }))
  const logs: RunLogEntry[] = (dto.logs ?? []).map((entry) => ({
    ts: entry.created_at,
    level: entry.level === 'warning' ? 'warn' : entry.level,
    nodeId: entry.node_key ?? undefined,
    message: entry.message,
  }))
  return {
    id: dto.id,
    pipelineId: dto.pipeline_id,
    status: dto.status,
    startedAt: dto.started_at ?? dto.created_at,
    finishedAt: dto.completed_at ?? undefined,
    durationMs:
      dto.started_at && dto.completed_at
        ? new Date(dto.completed_at).getTime() - new Date(dto.started_at).getTime()
        : undefined,
    correlationId: dto.correlation_id,
    trigger: dto.trigger,
    progress: dto.progress,
    nodeStates: states,
    logs,
    attempt: dto.current_attempt,
    rowsProcessed: dto.rows_processed,
    errorMessage: dto.safe_error_message ?? undefined,
  }
}

function mapArtifact(dto: ArtifactDto): PipelineArtifact {
  return {
    id: dto.id,
    nodeKey: dto.node_key,
    contentType: dto.content_type,
    sizeBytes: dto.size_bytes,
    sha256: dto.sha256,
    expiresAt: dto.expires_at,
    createdAt: dto.created_at,
  }
}

export interface PipelineSchedule {
  id: string
  pipelineId: string
  name: string
  scheduleType: string
  scheduleExpression: string | null
  timezone: string
  enabled: boolean
  status: string
  rowVersion: number
  lastRunAt: string | null
  nextRunAt: string | null
}

export interface PipelineScheduleInput {
  name: string
  scheduleType: 'one_time' | 'daily' | 'weekly' | 'monthly' | 'cron'
  scheduleExpression?: string | null
  timezone?: string
  runAt?: string | null
  enabled?: boolean
}

interface PipelineScheduleDto {
  id: string
  pipeline_id: string
  name: string
  schedule_type: string
  schedule_expression: string | null
  timezone: string
  enabled: boolean
  status: string
  row_version: number
  last_run_at: string | null
  next_run_at: string | null
}

function mapSchedule(dto: PipelineScheduleDto): PipelineSchedule {
  return {
    id: dto.id,
    pipelineId: dto.pipeline_id,
    name: dto.name,
    scheduleType: dto.schedule_type,
    scheduleExpression: dto.schedule_expression,
    timezone: dto.timezone,
    enabled: dto.enabled,
    status: dto.status,
    rowVersion: dto.row_version,
    lastRunAt: dto.last_run_at,
    nextRunAt: dto.next_run_at,
  }
}

export const pipelineService = {
  async list(): Promise<PipelineListItem[]> {
    const page = await apiClient.get<{ items: SummaryDto[] }>('/api/v1/pipelines')
    return page.items.map(mapSummary)
  },
  async get(id: string): Promise<Pipeline> {
    return mapEditor(await apiClient.get<EditorDto>(`/api/v1/pipelines/${id}`))
  },
  async create(draft: Pipeline): Promise<Pipeline> {
    return mapEditor(await apiClient.post<EditorDto>('/api/v1/pipelines', graphBody(draft)))
  },
  async save(pipeline: Pipeline): Promise<Pipeline> {
    return mapEditor(await apiClient.put<EditorDto>(`/api/v1/pipelines/${pipeline.id}`, saveBody(pipeline)))
  },
  async publish(pipeline: Pipeline): Promise<{ version: number }> {
    const response = await apiClient.post<{ version_number: number }>(`/api/v1/pipelines/${pipeline.id}/publish`, {
      expected_version: pipeline.rowVersion,
      change_summary: 'Published from Pipeline Studio',
    })
    return { version: response.version_number }
  },
  async versions(id: string): Promise<Array<{ id: string; version_number: number; created_at: string }>> {
    return apiClient.get(`/api/v1/pipelines/${id}/versions`)
  },
  async validate(id: string): Promise<ValidationReport> {
    const response = await apiClient.post<{
      valid: boolean
      errors: Array<{ code: string; message: string; node_key?: string }>
      warnings: Array<{ code: string; message: string; node_key?: string }>
    }>(`/api/v1/pipelines/${id}/validate`)
    return {
      valid: response.valid,
      checkedAt: new Date().toISOString(),
      issues: [
        ...response.errors.map((issue) => ({ ...issue, level: 'error' as const })),
        ...response.warnings.map((issue) => ({ ...issue, level: 'warning' as const })),
      ].map((issue, index) => ({
        id: `${issue.code}-${index}`,
        code: issue.code,
        message: issue.message,
        level: issue.level,
        scope: issue.node_key ? 'node' : 'pipeline',
        nodeId: issue.node_key,
      })),
    }
  },
  async startRun(id: string): Promise<PipelineRun> {
    return mapRun(await apiClient.post<RunDto>(`/api/v1/pipelines/${id}/runs`, {}))
  },
  async getRun(pipelineId: string, runId: string, signal?: AbortSignal): Promise<PipelineRun> {
    return mapRun(await apiClient.get<RunDto>(`/api/v1/pipelines/${pipelineId}/runs/${runId}`, { signal }))
  },
  async listRuns(id: string): Promise<PipelineRun[]> {
    const page = await apiClient.get<{ items: RunDto[] }>(`/api/v1/pipelines/${id}/runs`)
    return page.items.map(mapRun)
  },
  async cancelRun(pipelineId: string, runId: string): Promise<PipelineRun> {
    return mapRun(await apiClient.post<RunDto>(`/api/v1/pipelines/${pipelineId}/runs/${runId}/cancel`))
  },
  async retryRun(pipelineId: string, runId: string): Promise<PipelineRun> {
    return mapRun(await apiClient.post<RunDto>(`/api/v1/pipelines/${pipelineId}/runs/${runId}/retry`))
  },
  async listArtifacts(pipelineId: string, runId: string): Promise<PipelineArtifact[]> {
    const rows = await apiClient.get<ArtifactDto[]>(`/api/v1/pipelines/${pipelineId}/runs/${runId}/artifacts`)
    return rows.map(mapArtifact)
  },
  async createArtifactDownloadUrl(
    pipelineId: string,
    runId: string,
    artifactId: string,
  ): Promise<ArtifactDownloadLink> {
    const link = await apiClient.post<{ url: string; expires_in_seconds: number }>(
      `/api/v1/pipelines/${pipelineId}/runs/${runId}/artifacts/${artifactId}/download-url`,
    )
    return { url: link.url, expiresInSeconds: link.expires_in_seconds }
  },
  // Backend implements DELETE as a soft-archive (sets archived_at); requires the
  // current version for optimistic concurrency. There is no separate pipeline
  // archive endpoint and no restore/unarchive endpoint.
  async remove(id: string, expectedVersion: number): Promise<void> {
    await apiClient.delete(`/api/v1/pipelines/${id}?expected_version=${expectedVersion}`)
  },
  // --- Run schedules (post-Core P1) ---
  async listSchedules(pipelineId: string): Promise<PipelineSchedule[]> {
    const rows = await apiClient.get<PipelineScheduleDto[]>(`/api/v1/pipelines/${pipelineId}/schedules`)
    return rows.map(mapSchedule)
  },
  async createSchedule(pipelineId: string, input: PipelineScheduleInput): Promise<PipelineSchedule> {
    return mapSchedule(
      await apiClient.post<PipelineScheduleDto>(`/api/v1/pipelines/${pipelineId}/schedules`, {
        name: input.name,
        schedule_type: input.scheduleType,
        schedule_expression: input.scheduleExpression ?? null,
        timezone: input.timezone ?? 'UTC',
        run_at: input.runAt ?? null,
        enabled: input.enabled ?? true,
      }),
    )
  },
  async updateSchedule(
    pipelineId: string,
    scheduleId: string,
    input: Partial<PipelineScheduleInput> & { expectedVersion: number },
  ): Promise<PipelineSchedule> {
    return mapSchedule(
      await apiClient.put<PipelineScheduleDto>(`/api/v1/pipelines/${pipelineId}/schedules/${scheduleId}`, {
        expected_version: input.expectedVersion,
        name: input.name,
        schedule_type: input.scheduleType,
        schedule_expression: input.scheduleExpression,
        timezone: input.timezone,
        run_at: input.runAt,
        enabled: input.enabled,
      }),
    )
  },
  /** Pause/resume by toggling `enabled` (the same mechanism as delivery schedules). */
  async toggleSchedule(pipelineId: string, schedule: PipelineSchedule, enabled: boolean): Promise<PipelineSchedule> {
    return this.updateSchedule(pipelineId, schedule.id, {
      expectedVersion: schedule.rowVersion,
      enabled,
    })
  },
  async deleteSchedule(pipelineId: string, scheduleId: string, expectedVersion: number): Promise<void> {
    await apiClient.delete(
      `/api/v1/pipelines/${pipelineId}/schedules/${scheduleId}?expected_version=${expectedVersion}`,
    )
  },
}

export function newDraft(): Pipeline {
  return {
    id: 'new',
    name: 'Untitled pipeline',
    description: '',
    status: 'draft',
    version: 0,
    rowVersion: 1,
    owner: 'You',
    tags: [],
    nodes: [],
    edges: [],
    canvas: { x: 40, y: 40, scale: 1, snapGrid: true, initialized: false },
    updatedAt: new Date().toISOString(),
  }
}
