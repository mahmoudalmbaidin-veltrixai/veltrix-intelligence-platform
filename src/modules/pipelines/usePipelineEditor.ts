/**
 * Pipeline editor engine. Owns the editable graph and every interaction:
 * add/move/duplicate/delete nodes, connect/delete edges, multi-select,
 * copy/paste, undo/redo, validation, dirty tracking and autosave.
 *
 * Kept as a composable (not a page) so state lives outside components and can
 * be unit-tested in isolation.
 */
import { computed, reactive, ref } from 'vue'
import type {
  Pipeline,
  PipelineNode,
  PipelineNodeKind,
  ValidationIssue,
  ValidationReport,
} from '@/shared/types/pipeline'
import { NODE_TYPES, mockOutputSchema } from './nodeTypes'
import { clone } from '@/shared/lib/mock'

let uid = 0
function genId(prefix: string): string {
  uid += 1
  return `${prefix}_${Date.now().toString(36)}${uid}`
}

export function usePipelineEditor(initial: Pipeline) {
  const pipeline = reactive<Pipeline>(clone(initial))
  const selection = ref<Set<string>>(new Set())
  const selectedEdge = ref<string | null>(null)

  // history stacks store JSON snapshots of {nodes, edges}
  const undoStack = ref<string[]>([])
  const redoStack = ref<string[]>([])
  const clipboard = ref<PipelineNode[]>([])
  const dirty = ref(false)
  // Propagate schemas once on load so downstream Select/Rename/Formula editors
  // receive upstream columns immediately (source nodes carry their restored
  // outputSchema). This runs before the saved snapshot is captured, so restoring
  // schema state never marks the freshly-loaded pipeline dirty.
  propagateSchemas()
  const lastSavedSnapshot = ref(snapshot())

  function snapshot(): string {
    return JSON.stringify({
      nodes: pipeline.nodes,
      edges: pipeline.edges,
      canvas: pipeline.canvas,
      name: pipeline.name,
      description: pipeline.description,
    })
  }

  function commit() {
    undoStack.value.push(snapshot())
    if (undoStack.value.length > 100) undoStack.value.shift()
    redoStack.value = []
    // A commit always precedes a mutation, so the graph is about to diverge
    // from the last saved snapshot.
    dirty.value = true
  }

  function restore(snap: string) {
    const parsed = JSON.parse(snap) as Pick<Pipeline, 'nodes' | 'edges' | 'canvas' | 'name' | 'description'>
    pipeline.nodes = parsed.nodes
    pipeline.edges = parsed.edges
    Object.assign(pipeline.canvas, parsed.canvas)
    pipeline.name = parsed.name
    pipeline.description = parsed.description
    propagateSchemas()
    dirty.value = snapshot() !== lastSavedSnapshot.value
  }

  function propagateSchemas() {
    const byId = new Map(pipeline.nodes.map((node) => [node.id, node]))
    for (let pass = 0; pass < pipeline.nodes.length; pass += 1) {
      for (const node of pipeline.nodes) {
        if (NODE_TYPES[node.kind].category === 'source') continue
        const incoming = pipeline.edges
          .filter((edge) => edge.targetNode === node.id)
          .flatMap((edge) => byId.get(edge.sourceNode)?.outputSchema ?? [])
        const unique = [...new Map(incoming.map((column) => [column.name, column])).values()]
        node.inputSchema = clone(unique)
        let output = clone(unique)
        if (node.kind === 'select-columns' && Array.isArray(node.config.columns)) {
          const selected = new Set(node.config.columns)
          output = output.filter((column) => selected.has(column.name))
        } else if (node.kind === 'rename-columns' && node.config.renames && typeof node.config.renames === 'object') {
          const renames = node.config.renames as Record<string, string>
          output = output.map((column) => ({ ...column, name: renames[column.name] ?? column.name }))
        } else if (node.kind === 'formula' && typeof node.config.field === 'string' && node.config.field) {
          output = [
            ...output.filter((column) => column.name !== node.config.field),
            { name: node.config.field, dataType: 'number' },
          ]
        } else if (node.kind === 'type-convert' && typeof node.config.field === 'string') {
          output = output.map((column) =>
            column.name === node.config.field
              ? { ...column, dataType: (node.config.target_type as typeof column.dataType) ?? column.dataType }
              : column,
          )
        }
        node.outputSchema = output
      }
    }
  }

  const canUndo = computed(() => undoStack.value.length > 0)
  const canRedo = computed(() => redoStack.value.length > 0)

  function undo() {
    if (!undoStack.value.length) return
    redoStack.value.push(snapshot())
    restore(undoStack.value.pop()!)
    selection.value = new Set()
  }
  function redo() {
    if (!redoStack.value.length) return
    undoStack.value.push(snapshot())
    restore(redoStack.value.pop()!)
    selection.value = new Set()
  }

  function markSaved() {
    lastSavedSnapshot.value = snapshot()
    dirty.value = false
  }

  /* ---- nodes ---- */
  function addNode(kind: PipelineNodeKind, x: number, y: number): PipelineNode {
    commit()
    const spec = NODE_TYPES[kind]
    const config: Record<string, unknown> = {}
    spec.config.forEach((c) => {
      if (c.defaultValue !== undefined) config[c.key] = c.defaultValue
    })
    const node: PipelineNode = {
      id: genId('n'),
      kind,
      title: spec.label,
      x: Math.round(x),
      y: Math.round(y),
      config,
      outputSchema: mockOutputSchema(kind),
    }
    pipeline.nodes.push(node)
    selection.value = new Set([node.id])
    return node
  }

  function moveNodes(ids: string[], dx: number, dy: number) {
    ids.forEach((id) => {
      const n = pipeline.nodes.find((x) => x.id === id)
      if (n) {
        n.x += dx
        n.y += dy
      }
    })
    dirty.value = true
  }

  function updateNodeConfig(id: string, key: string, value: unknown) {
    const n = pipeline.nodes.find((x) => x.id === id)
    if (!n) return
    commit()
    n.config = { ...n.config, [key]: value }
    propagateSchemas()
  }

  function updateNodeSource(id: string, config: Record<string, unknown>, outputSchema: PipelineNode['outputSchema']) {
    const n = pipeline.nodes.find((x) => x.id === id)
    if (!n) return
    commit()
    n.config = { ...n.config, ...config }
    n.outputSchema = clone(outputSchema ?? [])
    propagateSchemas()
  }

  function renameNode(id: string, title: string) {
    const n = pipeline.nodes.find((x) => x.id === id)
    if (!n) return
    commit()
    n.title = title
  }

  function deleteNodes(ids: string[]) {
    if (!ids.length) return
    commit()
    const set = new Set(ids)
    pipeline.nodes = pipeline.nodes.filter((n) => !set.has(n.id))
    pipeline.edges = pipeline.edges.filter((e) => !set.has(e.sourceNode) && !set.has(e.targetNode))
    selection.value = new Set()
  }

  function duplicateNodes(ids: string[]) {
    if (!ids.length) return
    commit()
    const created: string[] = []
    ids.forEach((id) => {
      const n = pipeline.nodes.find((x) => x.id === id)
      if (!n) return
      const copy: PipelineNode = { ...clone(n), id: genId('n'), x: n.x + 40, y: n.y + 40 }
      pipeline.nodes.push(copy)
      created.push(copy.id)
    })
    selection.value = new Set(created)
  }

  function copySelection() {
    clipboard.value = pipeline.nodes.filter((n) => selection.value.has(n.id)).map((n) => clone(n))
  }
  function paste() {
    if (!clipboard.value.length) return
    commit()
    const created: string[] = []
    clipboard.value.forEach((n) => {
      const copy: PipelineNode = { ...clone(n), id: genId('n'), x: n.x + 60, y: n.y + 60 }
      pipeline.nodes.push(copy)
      created.push(copy.id)
    })
    selection.value = new Set(created)
  }

  /* ---- edges ---- */
  function connect(sourceNode: string, sourcePort: string, targetNode: string, targetPort: string): boolean {
    if (sourceNode === targetNode) return false
    // one edge per target port
    const exists = pipeline.edges.some((e) => e.targetNode === targetNode && e.targetPort === targetPort)
    if (exists) return false
    // prevent trivial cycle
    if (pipeline.edges.some((e) => e.sourceNode === targetNode && e.targetNode === sourceNode)) return false
    commit()
    pipeline.edges.push({ id: genId('e'), sourceNode, sourcePort, targetNode, targetPort })
    propagateSchemas()
    return true
  }
  function deleteEdge(id: string) {
    commit()
    pipeline.edges = pipeline.edges.filter((e) => e.id !== id)
    propagateSchemas()
    if (selectedEdge.value === id) selectedEdge.value = null
  }

  /* ---- selection ---- */
  function selectNode(id: string, additive = false) {
    selectedEdge.value = null
    if (additive) {
      const next = new Set(selection.value)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      selection.value = next
    } else {
      selection.value = new Set([id])
    }
  }
  function selectMany(ids: string[]) {
    selectedEdge.value = null
    selection.value = new Set(ids)
  }
  /**
   * Selecting an edge clears node selection so edge/node selection is mutually
   * exclusive — Delete then removes exactly the focused element (QA VIP-FE-H006).
   */
  function selectEdge(id: string) {
    selection.value = new Set()
    selectedEdge.value = id
  }
  function clearSelection() {
    selection.value = new Set()
    selectedEdge.value = null
  }
  const selectedNode = computed<PipelineNode | null>(() => {
    if (selection.value.size !== 1) return null
    const id = [...selection.value][0]
    return pipeline.nodes.find((n) => n.id === id) ?? null
  })

  /* ---- validation ---- */
  function validate(): ValidationReport {
    const issues: ValidationIssue[] = []
    if (pipeline.nodes.length === 0) {
      issues.push({
        id: genId('iss'),
        level: 'error',
        scope: 'pipeline',
        code: 'EMPTY',
        message: 'Pipeline has no nodes.',
      })
    }
    const hasOutput = pipeline.nodes.some((n) => NODE_TYPES[n.kind].category === 'output')
    if (pipeline.nodes.length > 0 && !hasOutput) {
      issues.push({
        id: genId('iss'),
        level: 'warning',
        scope: 'pipeline',
        code: 'NO_OUTPUT',
        message: 'No output node — results will not be materialised.',
      })
    }

    pipeline.nodes.forEach((n) => {
      const spec = NODE_TYPES[n.kind]
      // required config
      spec.config.forEach((c) => {
        if (!c.required) return
        // skip conditionally hidden fields
        if (c.visibleWhen && n.config[c.visibleWhen.key] !== c.visibleWhen.equals) return
        const v = n.config[c.key]
        const empty =
          v == null ||
          v === '' ||
          (Array.isArray(v) && v.length === 0) ||
          (typeof v === 'object' && !Array.isArray(v) && Object.keys(v as object).length === 0)
        if (empty) {
          issues.push({
            id: genId('iss'),
            level: 'error',
            scope: 'node',
            nodeId: n.id,
            code: 'REQ',
            message: `${n.title}: “${c.label}” is required.`,
          })
        }
      })
      if (n.kind === 'source-dataset' && !n.config.dataset_id) {
        issues.push({
          id: genId('iss'),
          level: 'error',
          scope: 'node',
          nodeId: n.id,
          code: 'REQ',
          message: `${n.title}: a governed dataset is required.`,
        })
      }
      // disconnected (non-source with no input edge)
      if (spec.inputs.length > 0) {
        const incoming = pipeline.edges.filter((e) => e.targetNode === n.id)
        if (incoming.length === 0) {
          issues.push({
            id: genId('iss'),
            level: 'error',
            scope: 'node',
            nodeId: n.id,
            code: 'DISCONNECTED',
            message: `${n.title}: input is not connected.`,
          })
        } else {
          // required multi-input ports
          spec.inputs.forEach((port) => {
            if (!incoming.some((e) => e.targetPort === port.id)) {
              issues.push({
                id: genId('iss'),
                level: 'warning',
                scope: 'node',
                nodeId: n.id,
                code: 'PORT',
                message: `${n.title}: “${port.label}” input is empty.`,
              })
            }
          })
        }
      }
      // source with no downstream
      if (spec.category === 'source' && !pipeline.edges.some((e) => e.sourceNode === n.id)) {
        issues.push({
          id: genId('iss'),
          level: 'warning',
          scope: 'node',
          nodeId: n.id,
          code: 'UNUSED',
          message: `${n.title}: output is not used.`,
        })
      }
    })

    return { valid: !issues.some((i) => i.level === 'error'), issues, checkedAt: new Date().toISOString() }
  }

  const nodeIssues = computed(() => {
    const report = validate()
    const map = new Map<string, ValidationIssue[]>()
    report.issues.forEach((i) => {
      if (!i.nodeId) return
      if (!map.has(i.nodeId)) map.set(i.nodeId, [])
      map.get(i.nodeId)!.push(i)
    })
    return map
  })

  return {
    pipeline,
    selection,
    selectedNode,
    selectedEdge,
    dirty,
    canUndo,
    canRedo,
    clipboard,
    addNode,
    moveNodes,
    updateNodeConfig,
    updateNodeSource,
    renameNode,
    deleteNodes,
    duplicateNodes,
    copySelection,
    paste,
    connect,
    deleteEdge,
    selectNode,
    selectMany,
    selectEdge,
    clearSelection,
    undo,
    redo,
    commit,
    markSaved,
    validate,
    nodeIssues,
  }
}

export type PipelineEditor = ReturnType<typeof usePipelineEditor>
