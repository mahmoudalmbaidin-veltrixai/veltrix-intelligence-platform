/**
 * Pipeline service (mock + local persistence).
 *
 * INTEGRATION POINT
 *   GET    /api/v1/pipelines                 -> PipelineListItem[]
 *   GET    /api/v1/pipelines/:id             -> Pipeline
 *   PUT    /api/v1/pipelines/:id             -> Pipeline   (save draft)
 *   POST   /api/v1/pipelines/:id/publish     -> Pipeline
 *   POST   /api/v1/pipelines/:id/runs        -> PipelineRun (start run)
 *   Required permission: pipeline:read / pipeline:write / pipeline:run / pipeline:publish
 *
 * Editor state persists to localStorage so canvas work survives reloads.
 * Secrets are never stored here.
 */
import type { Pipeline, PipelineListItem, PipelineRun } from '@/shared/types/pipeline'
import { LocalStore, latency, isoAgo, isoAhead, nowIso, clone } from '@/shared/lib/mock'
import { ApiError } from '@/shared/types/api'
import { SEED_PIPELINES } from './seed'

const store = new LocalStore<Record<string, Pipeline>>('vip.pipelines')

function db(): Record<string, Pipeline> {
  const existing = store.read({})
  if (Object.keys(existing).length === 0) {
    const seeded: Record<string, Pipeline> = {}
    SEED_PIPELINES.forEach((p) => (seeded[p.id] = p))
    store.write(seeded)
    return seeded
  }
  return existing
}

function toListItem(p: Pipeline): PipelineListItem {
  return {
    id: p.id, name: p.name, status: p.status, owner: p.owner, tags: p.tags,
    version: p.version, updatedAt: p.updatedAt, lastRunAt: p.lastRunAt,
    lastRunStatus: p.lastRunStatus, nextSchedule: p.nextSchedule, nodeCount: p.nodes.length,
  }
}

export const pipelineService = {
  async list(): Promise<PipelineListItem[]> {
    await latency()
    return Object.values(db()).map(toListItem).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  },

  async get(id: string): Promise<Pipeline> {
    await latency(120, 320)
    const found = db()[id]
    if (!found) {
      // return a fresh empty draft for /pipelines/new or unknown ids
      if (id === 'new') return newDraft()
      throw new ApiError('not-found', `Pipeline ${id} not found`)
    }
    return clone(found)
  },

  async save(pipeline: Pipeline): Promise<Pipeline> {
    await latency(150, 380)
    const current = db()
    const saved: Pipeline = { ...pipeline, updatedAt: nowIso() }
    current[saved.id] = saved
    store.write(current)
    return clone(saved)
  },

  async publish(pipeline: Pipeline): Promise<Pipeline> {
    await latency(200, 480)
    const published: Pipeline = { ...pipeline, status: 'published', version: pipeline.version + 1, updatedAt: nowIso() }
    const current = db()
    current[published.id] = published
    store.write(current)
    return clone(published)
  },
}

export function newDraft(): Pipeline {
  return {
    id: `pl_${Math.random().toString(36).slice(2, 8)}`,
    name: 'Untitled pipeline',
    description: '',
    status: 'draft',
    version: 1,
    owner: 'You',
    tags: [],
    nodes: [],
    edges: [],
    updatedAt: nowIso(),
  }
}

/* -------- Run simulation --------
   Produces a live-updating run by advancing node states in topological order. */
export function createRun(pipeline: Pipeline, trigger: PipelineRun['trigger'] = 'manual', attempt = 1): PipelineRun {
  return {
    id: `run_${Math.random().toString(36).slice(2, 9)}`,
    pipelineId: pipeline.id,
    status: 'queued',
    startedAt: nowIso(),
    correlationId: crypto.randomUUID().slice(0, 13),
    trigger,
    progress: 0,
    nodeStates: pipeline.nodes.map((n) => ({ nodeId: n.id, status: 'queued' })),
    logs: [{ ts: nowIso(), level: 'info', message: `Run queued (attempt ${attempt}) · trigger: ${trigger}` }],
    attempt,
    rowsProcessed: 0,
  }
}

export const RECENT_RUNS: (pipelineId: string) => PipelineRun[] = (pipelineId) => [
  {
    id: 'run_a1', pipelineId, status: 'succeeded', startedAt: isoAgo(180), finishedAt: isoAgo(176),
    durationMs: 242_000, correlationId: 'c-8f21a90b3', trigger: 'schedule', progress: 100,
    nodeStates: [], logs: [], attempt: 1, rowsProcessed: 2_412_880,
  },
  {
    id: 'run_a2', pipelineId, status: 'failed', startedAt: isoAgo(60), finishedAt: isoAgo(58),
    durationMs: 96_000, correlationId: 'c-1b7742de5', trigger: 'schedule', progress: 64,
    nodeStates: [], logs: [], attempt: 1, rowsProcessed: 1_100_400,
  },
  {
    id: 'run_a3', pipelineId, status: 'running', startedAt: isoAgo(3), correlationId: 'c-4a09fe112',
    trigger: 'manual', progress: 42, nodeStates: [], logs: [], attempt: 2, rowsProcessed: 640_200,
  },
]

export const NEXT_SCHEDULE = isoAhead(360)
