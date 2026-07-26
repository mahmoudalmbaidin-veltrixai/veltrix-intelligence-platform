import { describe, it, expect, beforeEach } from 'vitest'
import { usePipelineEditor } from './usePipelineEditor'
import { newDraft } from './pipelines.service'
import type { Pipeline } from '@/shared/types/pipeline'

function fresh(): Pipeline {
  return { ...newDraft(), id: 'pl_test' }
}

describe('usePipelineEditor', () => {
  let editor: ReturnType<typeof usePipelineEditor>
  beforeEach(() => {
    editor = usePipelineEditor(fresh())
  })

  it('creates a node on the canvas', () => {
    const n = editor.addNode('source-dataset', 100, 120)
    expect(editor.pipeline.nodes).toHaveLength(1)
    expect(n.kind).toBe('source-dataset')
    expect(editor.selection.value.has(n.id)).toBe(true)
  })

  it('moves a node by a delta', () => {
    const n = editor.addNode('filter', 100, 100)
    editor.moveNodes([n.id], 40, -20)
    expect(n.x).toBe(140)
    expect(n.y).toBe(80)
  })

  it('creates an edge between two nodes', () => {
    const a = editor.addNode('source-dataset', 0, 0)
    const b = editor.addNode('filter', 300, 0)
    const ok = editor.connect(a.id, 'out', b.id, 'in')
    expect(ok).toBe(true)
    expect(editor.pipeline.edges).toHaveLength(1)
  })

  it('prevents duplicate edges into the same target port', () => {
    const a = editor.addNode('source-dataset', 0, 0)
    const b = editor.addNode('filter', 300, 0)
    editor.connect(a.id, 'out', b.id, 'in')
    const second = editor.connect(a.id, 'out', b.id, 'in')
    expect(second).toBe(false)
    expect(editor.pipeline.edges).toHaveLength(1)
  })

  it('selects nodes additively', () => {
    const a = editor.addNode('source-dataset', 0, 0)
    const b = editor.addNode('filter', 300, 0)
    editor.selectNode(a.id)
    editor.selectNode(b.id, true)
    expect(editor.selection.value.size).toBe(2)
  })

  it('supports undo and redo', () => {
    editor.addNode('source-dataset', 0, 0)
    expect(editor.pipeline.nodes).toHaveLength(1)
    editor.addNode('filter', 200, 0)
    expect(editor.pipeline.nodes).toHaveLength(2)
    editor.undo()
    expect(editor.pipeline.nodes).toHaveLength(1)
    editor.redo()
    expect(editor.pipeline.nodes).toHaveLength(2)
  })

  it('restores edges and canvas state through undo and redo', () => {
    const source = editor.addNode('source-dataset', 0, 0)
    const target = editor.addNode('filter', 300, 0)
    editor.connect(source.id, 'out', target.id, 'in')
    editor.markSaved()
    editor.commit()
    editor.pipeline.canvas.x = 180
    editor.pipeline.canvas.y = 90
    editor.pipeline.canvas.scale = 1.4
    editor.deleteEdge(editor.pipeline.edges[0].id)
    expect(editor.pipeline.edges).toHaveLength(0)
    editor.undo()
    expect(editor.pipeline.edges).toHaveLength(1)
    editor.undo()
    expect(editor.pipeline.canvas.x).toBe(40)
    editor.redo()
    expect(editor.pipeline.canvas.x).toBe(180)
  })

  it('deletes nodes and their connected edges', () => {
    const a = editor.addNode('source-dataset', 0, 0)
    const b = editor.addNode('filter', 300, 0)
    editor.connect(a.id, 'out', b.id, 'in')
    editor.deleteNodes([a.id])
    expect(editor.pipeline.nodes).toHaveLength(1)
    expect(editor.pipeline.edges).toHaveLength(0)
  })

  it('duplicates a node offset from the original', () => {
    const a = editor.addNode('filter', 100, 100)
    editor.duplicateNodes([a.id])
    expect(editor.pipeline.nodes).toHaveLength(2)
    const copy = editor.pipeline.nodes[1]
    expect(copy.x).toBe(140)
    expect(copy.id).not.toBe(a.id)
  })

  it('copies and pastes nodes', () => {
    const a = editor.addNode('filter', 0, 0)
    editor.selectNode(a.id)
    editor.copySelection()
    editor.paste()
    expect(editor.pipeline.nodes).toHaveLength(2)
  })

  it('flags a disconnected transform node as an error', () => {
    editor.addNode('filter', 0, 0)
    const report = editor.validate()
    expect(report.valid).toBe(false)
    expect(report.issues.some((i) => i.code === 'DISCONNECTED')).toBe(true)
  })

  it('flags missing required configuration', () => {
    editor.addNode('source-dataset', 0, 0) // requires a dataset ID
    const report = editor.validate()
    expect(report.issues.some((i) => i.code === 'REQ')).toBe(true)
  })

  it('persists a governed source reference and schema through undo and redo', () => {
    const editor = usePipelineEditor(fresh())
    const node = editor.addNode('source-dataset', 0, 0)
    editor.updateNodeSource(
      node.id,
      {
        source_type: 'dataset',
        dataset_id: 'dataset-1',
        dataset_version: 3,
        columns: ['order_id'],
        schema_snapshot: [{ name: 'order_id', type: 'bigint', nullable: false }],
      },
      [{ name: 'order_id', dataType: 'integer' }],
    )
    expect(editor.selectedNode.value?.config.dataset_id).toBe('dataset-1')
    expect(editor.selectedNode.value?.outputSchema).toEqual([{ name: 'order_id', dataType: 'integer' }])

    editor.undo()
    expect(editor.selectedNode.value).toBeNull()
    editor.redo()
    const restored = editor.pipeline.nodes.find((item) => item.id === node.id)
    expect(restored?.config.dataset_version).toBe(3)
    expect(restored?.outputSchema?.[0]?.name).toBe('order_id')
  })

  it('makes edge and node selection mutually exclusive (VIP-FE-H006)', () => {
    const a = editor.addNode('source-dataset', 0, 0)
    const b = editor.addNode('filter', 300, 0)
    const ok = editor.connect(a.id, 'out', b.id, 'in')
    expect(ok).toBe(true)
    const edgeId = editor.pipeline.edges[0].id
    editor.selectNode(a.id)
    expect(editor.selection.value.size).toBe(1)
    // Selecting an edge must clear the node selection so Delete is unambiguous.
    editor.selectEdge(edgeId)
    expect(editor.selection.value.size).toBe(0)
    expect(editor.selectedEdge.value).toBe(edgeId)
    // And re-selecting a node clears the edge.
    editor.selectNode(b.id)
    expect(editor.selectedEdge.value).toBeNull()
  })

  it('tracks dirty state and clears it on markSaved', () => {
    editor.addNode('filter', 0, 0)
    expect(editor.dirty.value).toBe(true)
    editor.markSaved()
    expect(editor.dirty.value).toBe(false)
  })
})
