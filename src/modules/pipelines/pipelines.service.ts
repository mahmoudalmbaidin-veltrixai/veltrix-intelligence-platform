/** Live B7 pipeline REST adapter. No production-path seeds or local persistence. */
import { apiClient } from '@/shared/lib/apiClient'
import type {
  Pipeline,
  PipelineListItem,
  PipelineNode,
  PipelineRun,
  RunLogEntry,
  RunNodeState,
  ValidationReport,
} from '@/shared/types/pipeline'

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
interface EditorDto {
  pipeline: SummaryDto
  canvas: Record<string, unknown>
  nodes: NodeDto[]
  edges: EdgeDto[]
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

const nodeId = (node: NodeDto) => node.key
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
    nodes: dto.nodes.map((node) => ({
      id: nodeId(node),
      kind: node.type,
      title: node.title,
      x: node.x,
      y: node.y,
      config: node.config,
    })),
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
function saveBody(pipeline: Pipeline) {
  return {
    name: pipeline.name,
    description: pipeline.description,
    tags: pipeline.tags,
    expected_version: pipeline.rowVersion,
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
    const created = mapEditor(
      await apiClient.post<EditorDto>('/api/v1/pipelines', {
        name: draft.name,
        description: draft.description,
        tags: draft.tags,
      }),
    )
    if (!draft.nodes.length && !draft.edges.length) return created
    return mapEditor(
      await apiClient.put<EditorDto>(
        `/api/v1/pipelines/${created.id}`,
        saveBody({ ...draft, ...created, nodes: draft.nodes, edges: draft.edges }),
      ),
    )
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
  async getRun(pipelineId: string, runId: string): Promise<PipelineRun> {
    return mapRun(await apiClient.get<RunDto>(`/api/v1/pipelines/${pipelineId}/runs/${runId}`))
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
  // Backend implements DELETE as a soft-archive (sets archived_at); requires the
  // current version for optimistic concurrency. There is no separate pipeline
  // archive endpoint and no restore/unarchive endpoint.
  async remove(id: string, expectedVersion: number): Promise<void> {
    await apiClient.delete(`/api/v1/pipelines/${id}?expected_version=${expectedVersion}`)
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
