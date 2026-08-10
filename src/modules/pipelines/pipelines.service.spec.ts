import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/shared/lib/apiClient', () => ({ apiClient: api }))

import { newDraft, pipelineService } from './pipelines.service'

describe('pipelineService first save', () => {
  beforeEach(() => vi.clearAllMocks())

  it('creates metadata and graph atomically with one POST and no follow-up PUT', async () => {
    const draft = newDraft()
    draft.name = 'Atomic pipeline'
    draft.nodes = [
      { id: 'source', kind: 'source-dataset', title: 'Source', x: 10, y: 20, config: { dataset_id: 'd1' } },
    ]
    api.post.mockResolvedValue({
      pipeline: {
        id: 'pipeline-1',
        name: draft.name,
        description: '',
        status: 'draft',
        tags: [],
        row_version: 1,
        published_version: null,
        node_count: 1,
        last_run_at: null,
        last_run_status: null,
        updated_at: '2026-08-10T00:00:00Z',
      },
      canvas: draft.canvas,
      nodes: [{ key: 'source', type: 'source-dataset', title: 'Source', x: 10, y: 20, config: { dataset_id: 'd1' } }],
      edges: [],
    })

    const saved = await pipelineService.create(draft)

    expect(saved.id).toBe('pipeline-1')
    expect(saved.nodes).toHaveLength(1)
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/pipelines',
      expect.objectContaining({
        name: 'Atomic pipeline',
        nodes: [expect.objectContaining({ key: 'source' })],
        edges: [],
        canvas: draft.canvas,
      }),
    )
    expect(api.put).not.toHaveBeenCalled()
  })
})
