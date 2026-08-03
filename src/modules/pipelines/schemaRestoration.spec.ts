import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Pipeline, PipelineNode } from '@/shared/types/pipeline'

// Mock the API client so we can drive mapEditor from a representative editor DTO.
vi.mock('@/shared/lib/apiClient', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

import { apiClient } from '@/shared/lib/apiClient'
import { pipelineService } from './pipelines.service'
import { usePipelineEditor } from './usePipelineEditor'

const SNAPSHOT = [
  { name: 'id', type: 'bigint', nullable: false },
  { name: 'amount', type: 'numeric', nullable: true },
  { name: 'created_at', type: 'timestamp', nullable: true },
]

/** A saved editor DTO: source (with persisted schema_snapshot) -> select. */
function editorDto() {
  return {
    pipeline: {
      id: 'pl_1',
      name: 'Loaded',
      description: '',
      status: 'draft',
      tags: [],
      row_version: 3,
      published_version: null,
      node_count: 2,
      last_run_at: null,
      last_run_status: null,
      updated_at: '2026-08-03T00:00:00Z',
    },
    canvas: {},
    nodes: [
      {
        key: 'src',
        type: 'source-dataset',
        title: 'Source',
        x: 0,
        y: 0,
        config: { dataset_id: 'ds_1', columns: ['id', 'amount', 'created_at'], schema_snapshot: SNAPSHOT },
      },
      {
        key: 'sel',
        type: 'select-columns',
        title: 'Select',
        x: 300,
        y: 0,
        config: { columns: ['id', 'amount'] },
      },
    ],
    edges: [{ key: 'e1', source: 'src', target: 'sel', source_port: 'out', target_port: 'in' }],
    access: { level: 'owner', can_view: true, can_edit: true, can_run: true, can_manage: true },
  }
}

describe('pipeline schema restoration on load', () => {
  beforeEach(() => vi.clearAllMocks())

  it('mapEditor rebuilds a source node outputSchema from schema_snapshot', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(editorDto())
    const pipeline = await pipelineService.get('pl_1')
    const source = pipeline.nodes.find((n) => n.kind === 'source-dataset')!
    expect(source.outputSchema).toEqual([
      { name: 'id', dataType: 'integer' },
      { name: 'amount', dataType: 'number' },
      { name: 'created_at', dataType: 'datetime' },
    ])
  })

  it('propagates schema to downstream editors on construction (no graph mutation)', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(editorDto())
    const pipeline = await pipelineService.get('pl_1')
    const editor = usePipelineEditor(pipeline)
    const select = editor.pipeline.nodes.find((n) => n.kind === 'select-columns')!
    // The Select editor sees all upstream columns without any user interaction...
    expect(select.inputSchema?.map((c) => c.name)).toEqual(['id', 'amount', 'created_at'])
    // ...and its restored selection filters the output to the saved columns.
    expect(select.outputSchema?.map((c) => c.name)).toEqual(['id', 'amount'])
    // Restoring schema must never mark a freshly-loaded pipeline dirty.
    expect(editor.dirty.value).toBe(false)
  })

  it('restores Rename mappings and renames the propagated output on load', () => {
    const loaded: Pipeline = build([
      source(),
      { id: 'rn', kind: 'rename-columns', title: 'Rename', x: 300, y: 0, config: { renames: { amount: 'total' } } },
    ])
    const editor = usePipelineEditor(loaded)
    const rename = editor.pipeline.nodes.find((n) => n.kind === 'rename-columns')!
    expect(rename.inputSchema?.map((c) => c.name)).toEqual(['id', 'amount'])
    expect(rename.outputSchema?.map((c) => c.name)).toEqual(['id', 'total'])
    expect((rename.config.renames as Record<string, string>).amount).toBe('total')
    expect(editor.dirty.value).toBe(false)
  })

  it('restores Formula field suggestions and expression on load', () => {
    const loaded: Pipeline = build([
      source(),
      { id: 'fx', kind: 'formula', title: 'Formula', x: 300, y: 0, config: { field: 'net', formula: 'amount * 2' } },
    ])
    const editor = usePipelineEditor(loaded)
    const formula = editor.pipeline.nodes.find((n) => n.kind === 'formula')!
    // Field suggestions come from the propagated upstream schema.
    expect(formula.inputSchema?.map((c) => c.name)).toEqual(['id', 'amount'])
    // The computed field is appended to the output; the saved expression persists.
    expect(formula.outputSchema?.some((c) => c.name === 'net')).toBe(true)
    expect(formula.config.formula).toBe('amount * 2')
  })

  it('surfaces no invented columns when the source schema is unavailable', () => {
    const bareSource: PipelineNode = {
      id: 'src',
      kind: 'source-dataset',
      title: 'Source',
      x: 0,
      y: 0,
      config: { dataset_id: 'ds_1' }, // no schema_snapshot / outputSchema
    }
    const loaded = build([
      bareSource,
      { id: 'sel', kind: 'select-columns', title: 'Select', x: 300, y: 0, config: { columns: ['id'] } },
    ])
    const editor = usePipelineEditor(loaded)
    const select = editor.pipeline.nodes.find((n) => n.kind === 'select-columns')!
    // Missing upstream schema -> empty input, not fabricated columns; saved config kept.
    expect(select.inputSchema ?? []).toEqual([])
    expect(select.config.columns).toEqual(['id'])
  })
})

function source(): PipelineNode {
  return {
    id: 'src',
    kind: 'source-dataset',
    title: 'Source',
    x: 0,
    y: 0,
    config: { dataset_id: 'ds_1' },
    outputSchema: [
      { name: 'id', dataType: 'integer' },
      { name: 'amount', dataType: 'number' },
    ],
  }
}

function build(nodes: PipelineNode[]): Pipeline {
  return {
    id: 'pl_1',
    name: 'Loaded',
    description: '',
    status: 'draft',
    version: 0,
    rowVersion: 1,
    owner: 'You',
    tags: [],
    nodes,
    edges: nodes.slice(1).map((n, i) => ({
      id: `e${i}`,
      sourceNode: nodes[0].id,
      sourcePort: 'out',
      targetNode: n.id,
      targetPort: 'in',
    })),
    canvas: { x: 0, y: 0, scale: 1, snapGrid: true, initialized: true },
    updatedAt: '2026-08-03T00:00:00Z',
  }
}
