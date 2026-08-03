<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import type { PipelineEditor } from './usePipelineEditor'
import type { NodeExecStatus, PipelineNodeKind } from '@/shared/types/pipeline'
import { NODE_TYPES } from './nodeTypes'
import PipelineNode from './PipelineNode.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import { announce } from '@/shared/composables/useAnnouncer'

const props = withDefaults(
  defineProps<{
    editor: PipelineEditor
    execStatuses?: Map<string, NodeExecStatus>
    currentNodeId?: string
    readonly?: boolean
  }>(),
  { readonly: false },
)

const NODE_W = 176
const NODE_H = 62

const root = ref<HTMLElement>()
const view = props.editor.pipeline.canvas
const snapGrid = computed({
  get: () => view.snapGrid,
  set: (value: boolean) => {
    props.editor.commit()
    view.snapGrid = value
    view.initialized = true
  },
})

/* ---- coordinate helpers ---- */
function screenToCanvas(clientX: number, clientY: number): { x: number; y: number } {
  const rect = root.value!.getBoundingClientRect()
  return { x: (clientX - rect.left - view.x) / view.scale, y: (clientY - rect.top - view.y) / view.scale }
}

function portPos(nodeId: string, port: string, kind: 'in' | 'out'): { x: number; y: number } {
  const node = props.editor.pipeline.nodes.find((n) => n.id === nodeId)
  if (!node) return { x: 0, y: 0 }
  const spec = NODE_TYPES[node.kind]
  const ports = kind === 'in' ? spec.inputs : spec.outputs
  const idx = Math.max(
    0,
    ports.findIndex((p) => p.id === port),
  )
  const count = ports.length || 1
  const gap = 18
  const totalH = (count - 1) * gap
  const startY = node.y + NODE_H / 2 - totalH / 2
  return { x: kind === 'in' ? node.x : node.x + NODE_W, y: startY + idx * gap }
}

function edgePath(sx: number, sy: number, tx: number, ty: number): string {
  const dx = Math.max(40, Math.abs(tx - sx) * 0.5)
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`
}

const edges = computed(() =>
  props.editor.pipeline.edges.map((e) => {
    const s = portPos(e.sourceNode, e.sourcePort, 'out')
    const t = portPos(e.targetNode, e.targetPort, 'in')
    return { id: e.id, d: edgePath(s.x, s.y, t.x, t.y), selected: props.editor.selectedEdge.value === e.id }
  }),
)

/* Local unwrapped accessors for the template (nested composable refs are not
   auto-unwrapped when read through a prop object). */
const selectionSet = computed(() => props.editor.selection.value)
function pickEdge(id: string) {
  props.editor.selectEdge(id)
}

/* ---- keyboard authoring (QA VIP-FE-C003) ---- */
const keyboardConnect = ref<{ nodeId: string; port: string } | null>(null)
function onNodeSelect(id: string) {
  props.editor.selectNode(id)
  const n = props.editor.pipeline.nodes.find((x) => x.id === id)
  announce(`Selected node ${n?.title ?? ''}. Use arrow keys to move, Delete to remove.`)
}
function onPortActivate({ nodeId, port, kind }: { nodeId: string; port: string; kind: 'in' | 'out' }) {
  const title = (id: string) => props.editor.pipeline.nodes.find((n) => n.id === id)?.title ?? id
  if (kind === 'out') {
    keyboardConnect.value = { nodeId, port }
    announce(
      `Connection started from ${title(nodeId)}. Activate a target input port to connect, or press Escape to cancel.`,
    )
  } else {
    if (!keyboardConnect.value) {
      announce('Activate an output port first to start a connection.')
      return
    }
    const from = keyboardConnect.value
    const ok = props.editor.connect(from.nodeId, from.port, nodeId, port)
    announce(ok ? `Connected ${title(from.nodeId)} to ${title(nodeId)}.` : 'Could not create that connection.')
    keyboardConnect.value = null
  }
}
/** Called by the studio when Escape is pressed. */
function cancelKeyboardConnect() {
  if (keyboardConnect.value) {
    keyboardConnect.value = null
    announce('Connection cancelled.')
  }
}
defineExpose({ fitToScreen, zoomBy, cancelKeyboardConnect })

/* ---- pending connection ---- */
const pending = ref<{ nodeId: string; port: string; sx: number; sy: number; mx: number; my: number } | null>(null)
const pendingPath = computed(() =>
  pending.value ? edgePath(pending.value.sx, pending.value.sy, pending.value.mx, pending.value.my) : '',
)

/* ---- marquee ---- */
const marquee = ref<{ x0: number; y0: number; x1: number; y1: number } | null>(null)

/* ---- interaction state ---- */
let mode: 'idle' | 'pan' | 'drag' | 'connect' | 'marquee' = 'idle'
let dragStart = { x: 0, y: 0 }
let panStart = { x: 0, y: 0 }
let movedIds: string[] = []
let graphMoved = false

function onNodePointerDown({ id, event }: { id: string; event: PointerEvent }) {
  const additive = event.shiftKey || event.metaKey || event.ctrlKey
  if (!props.editor.selection.value.has(id)) props.editor.selectNode(id, additive)
  else if (additive) props.editor.selectNode(id, true)
  if (props.readonly) return
  mode = 'drag'
  graphMoved = false
  movedIds = [...props.editor.selection.value]
  dragStart = screenToCanvas(event.clientX, event.clientY)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}

function onPortPointerDown({
  nodeId,
  port,
  kind,
  event,
}: {
  nodeId: string
  port: string
  kind: 'in' | 'out'
  event: PointerEvent
}) {
  if (props.readonly || kind !== 'out') return
  const p = portPos(nodeId, port, 'out')
  const c = screenToCanvas(event.clientX, event.clientY)
  pending.value = { nodeId, port, sx: p.x, sy: p.y, mx: c.x, my: c.y }
  mode = 'connect'
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}

function onPortPointerUp({ nodeId, port, kind }: { nodeId: string; port: string; kind: 'in' | 'out' }) {
  if (!props.readonly && mode === 'connect' && pending.value && kind === 'in') {
    props.editor.connect(pending.value.nodeId, pending.value.port, nodeId, port)
  }
  pending.value = null
  mode = 'idle'
}

function onBackgroundPointerDown(event: PointerEvent) {
  if (event.button === 1 || event.shiftKey === false) {
    // left-drag on empty = pan; shift+drag = marquee
    if (event.shiftKey) {
      const c = screenToCanvas(event.clientX, event.clientY)
      marquee.value = { x0: c.x, y0: c.y, x1: c.x, y1: c.y }
      mode = 'marquee'
    } else {
      mode = 'pan'
      graphMoved = false
      panStart = { x: event.clientX - view.x, y: event.clientY - view.y }
      props.editor.clearSelection()
    }
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
  }
}

function onPointerMove(event: PointerEvent) {
  if (mode === 'pan') {
    if (!graphMoved) {
      props.editor.commit()
      graphMoved = true
    }
    view.x = event.clientX - panStart.x
    view.y = event.clientY - panStart.y
    view.initialized = true
  } else if (mode === 'drag') {
    const c = screenToCanvas(event.clientX, event.clientY)
    let dx = c.x - dragStart.x
    let dy = c.y - dragStart.y
    if (snapGrid.value) {
      dx = Math.round(dx / 16) * 16
      dy = Math.round(dy / 16) * 16
    }
    if (dx || dy) {
      if (!graphMoved) {
        props.editor.commit()
        graphMoved = true
      }
      props.editor.moveNodes(movedIds, dx, dy)
      dragStart = { x: dragStart.x + dx, y: dragStart.y + dy }
    }
  } else if (mode === 'connect' && pending.value) {
    const c = screenToCanvas(event.clientX, event.clientY)
    pending.value.mx = c.x
    pending.value.my = c.y
  } else if (mode === 'marquee' && marquee.value) {
    const c = screenToCanvas(event.clientX, event.clientY)
    marquee.value.x1 = c.x
    marquee.value.y1 = c.y
  }
}

function onPointerUp() {
  if (mode === 'marquee' && marquee.value) {
    const { x0, y0, x1, y1 } = marquee.value
    const minX = Math.min(x0, x1),
      maxX = Math.max(x0, x1),
      minY = Math.min(y0, y1),
      maxY = Math.max(y0, y1)
    const hits = props.editor.pipeline.nodes
      .filter((n) => n.x + NODE_W > minX && n.x < maxX && n.y + NODE_H > minY && n.y < maxY)
      .map((n) => n.id)
    props.editor.selectMany(hits)
    marquee.value = null
  }
  if (mode === 'connect') pending.value = null
  mode = 'idle'
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
}

/* ---- zoom ---- */
function onWheel(event: WheelEvent) {
  event.preventDefault()
  props.editor.commit()
  const rect = root.value!.getBoundingClientRect()
  const mx = event.clientX - rect.left
  const my = event.clientY - rect.top
  const delta = -event.deltaY * 0.0015
  const next = Math.min(2, Math.max(0.3, view.scale * (1 + delta)))
  const ratio = next / view.scale
  view.x = mx - (mx - view.x) * ratio
  view.y = my - (my - view.y) * ratio
  view.scale = next
  view.initialized = true
}

function zoomBy(factor: number) {
  props.editor.commit()
  const rect = root.value!.getBoundingClientRect()
  const mx = rect.width / 2
  const my = rect.height / 2
  const next = Math.min(2, Math.max(0.3, view.scale * factor))
  const ratio = next / view.scale
  view.x = mx - (mx - view.x) * ratio
  view.y = my - (my - view.y) * ratio
  view.scale = next
  view.initialized = true
}

function fitToScreen() {
  props.editor.commit()
  const nodes = props.editor.pipeline.nodes
  if (!nodes.length || !root.value) {
    view.scale = 1
    view.x = 40
    view.y = 40
    view.initialized = true
    return
  }
  const minX = Math.min(...nodes.map((n) => n.x)) - 40
  const minY = Math.min(...nodes.map((n) => n.y)) - 40
  const maxX = Math.max(...nodes.map((n) => n.x + NODE_W)) + 40
  const maxY = Math.max(...nodes.map((n) => n.y + NODE_H)) + 40
  const rect = root.value.getBoundingClientRect()
  const scale = Math.min(2, Math.max(0.3, Math.min(rect.width / (maxX - minX), rect.height / (maxY - minY))))
  view.scale = scale
  view.x = -minX * scale + (rect.width - (maxX - minX) * scale) / 2
  view.y = -minY * scale + (rect.height - (maxY - minY) * scale) / 2
  view.initialized = true
}

/* ---- drop from palette ---- */
function onDrop(event: DragEvent) {
  event.preventDefault()
  if (props.readonly) return
  const kind = event.dataTransfer?.getData('application/vip-node') as PipelineNodeKind
  if (!kind || !NODE_TYPES[kind]) return
  const c = screenToCanvas(event.clientX, event.clientY)
  props.editor.addNode(kind, c.x - NODE_W / 2, c.y - NODE_H / 2)
}

/* ---- minimap ---- */
const bounds = computed(() => {
  const nodes = props.editor.pipeline.nodes
  if (!nodes.length) return { minX: 0, minY: 0, w: 1000, h: 700 }
  const minX = Math.min(...nodes.map((n) => n.x)) - 60
  const minY = Math.min(...nodes.map((n) => n.y)) - 60
  const maxX = Math.max(...nodes.map((n) => n.x + NODE_W)) + 60
  const maxY = Math.max(...nodes.map((n) => n.y + NODE_H)) + 60
  return { minX, minY, w: Math.max(400, maxX - minX), h: Math.max(300, maxY - minY) }
})

onMounted(() => {
  if (!view.initialized) setTimeout(fitToScreen, 60)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})
</script>

<template>
  <div
    ref="root"
    class="pcanvas"
    :style="{
      backgroundSize: `${20 * view.scale}px ${20 * view.scale}px`,
      backgroundPosition: `${view.x}px ${view.y}px`,
    }"
    @pointerdown.self="onBackgroundPointerDown"
    @wheel="onWheel"
    @dragover.prevent
    @drop="onDrop"
  >
    <!-- transform layer -->
    <div class="pcanvas__layer" :style="{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }">
      <svg class="pcanvas__edges" :style="{ overflow: 'visible' }">
        <path
          v-for="e in edges"
          :key="e.id"
          :d="e.d"
          class="pcanvas__edge"
          :class="{ 'is-selected': e.selected }"
          @pointerdown.stop="pickEdge(e.id)"
          @dblclick.stop="editor.deleteEdge(e.id)"
        />
        <path v-if="pendingPath" :d="pendingPath" class="pcanvas__edge is-pending" />
        <rect
          v-if="marquee"
          :x="Math.min(marquee.x0, marquee.x1)"
          :y="Math.min(marquee.y0, marquee.y1)"
          :width="Math.abs(marquee.x1 - marquee.x0)"
          :height="Math.abs(marquee.y1 - marquee.y0)"
          class="pcanvas__marquee"
        />
      </svg>

      <PipelineNode
        v-for="node in editor.pipeline.nodes"
        :key="node.id"
        :node="node"
        :selected="selectionSet.has(node.id)"
        :issues="editor.nodeIssues.value.get(node.id)"
        :exec-status="execStatuses?.get(node.id)"
        @node-pointer-down="onNodePointerDown"
        @port-pointer-down="onPortPointerDown"
        @port-pointer-up="onPortPointerUp"
        @node-select="onNodeSelect"
        @port-activate="onPortActivate"
      />
    </div>

    <!-- empty hint -->
    <div v-if="!editor.pipeline.nodes.length" class="pcanvas__empty">
      <VipIcon name="workflow" :size="30" />
      <p>Drag a node from the palette to begin building your pipeline</p>
    </div>

    <!-- zoom controls -->
    <div class="pcanvas__controls">
      <button title="Zoom in" @click="zoomBy(1.2)"><VipIcon name="zoomIn" :size="16" /></button>
      <button title="Zoom out" @click="zoomBy(0.83)"><VipIcon name="zoomOut" :size="16" /></button>
      <button title="Fit to screen" @click="fitToScreen"><VipIcon name="fit" :size="16" /></button>
      <span class="pcanvas__zoom">{{ Math.round(view.scale * 100) }}%</span>
      <button title="Toggle snap-to-grid" :class="{ 'is-on': snapGrid }" @click="snapGrid = !snapGrid">
        <VipIcon name="grid" :size="16" />
      </button>
    </div>

    <!-- minimap -->
    <div class="pcanvas__minimap" aria-hidden="true">
      <svg :viewBox="`${bounds.minX} ${bounds.minY} ${bounds.w} ${bounds.h}`" preserveAspectRatio="xMidYMid meet">
        <rect
          v-for="node in editor.pipeline.nodes"
          :key="node.id"
          :x="node.x"
          :y="node.y"
          :width="NODE_W"
          :height="NODE_H"
          rx="6"
          class="pcanvas__mini-node"
          :class="{ 'is-selected': selectionSet.has(node.id) }"
        />
      </svg>
    </div>
  </div>
</template>

<style scoped>
.pcanvas {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: var(--vip-bg-canvas);
  background-image: radial-gradient(var(--vip-grid-dot) 1px, transparent 1px);
  cursor: default;
  touch-action: none;
}
.pcanvas__layer {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
}
.pcanvas__edges {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 1px;
  pointer-events: none;
}
.pcanvas__edge {
  fill: none;
  stroke: var(--vip-border-strong);
  stroke-width: 2;
  pointer-events: stroke;
  cursor: pointer;
}
.pcanvas__edge:hover {
  stroke: var(--vip-brand-400);
}
.pcanvas__edge.is-selected {
  stroke: var(--vip-brand-500);
  stroke-width: 2.5;
}
.pcanvas__edge.is-pending {
  stroke: var(--vip-brand-500);
  stroke-dasharray: 5 4;
}
.pcanvas__marquee {
  fill: var(--vip-brand-soft);
  stroke: var(--vip-brand-500);
  stroke-width: 1;
}

.pcanvas__empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--vip-sp-4);
  color: var(--vip-text-disabled);
  pointer-events: none;
}
.pcanvas__empty p {
  font-size: var(--vip-fs-md);
}

.pcanvas__controls {
  position: absolute;
  bottom: var(--vip-sp-5);
  left: var(--vip-sp-5);
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-2);
  box-shadow: var(--vip-shadow-md);
}
.pcanvas__controls button {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-secondary);
}
.pcanvas__controls button:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.pcanvas__controls button.is-on {
  background: var(--vip-brand-soft);
  color: var(--vip-brand-text);
}
.pcanvas__zoom {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  font-variant-numeric: tabular-nums;
  padding: 0 var(--vip-sp-3);
  min-width: 40px;
  text-align: center;
}

.pcanvas__minimap {
  position: absolute;
  bottom: var(--vip-sp-5);
  right: var(--vip-sp-5);
  width: 180px;
  height: 120px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border);
  border-radius: var(--vip-radius-md);
  padding: var(--vip-sp-3);
  box-shadow: var(--vip-shadow-md);
  opacity: 0.94;
}
.pcanvas__minimap svg {
  width: 100%;
  height: 100%;
}
.pcanvas__mini-node {
  fill: var(--vip-text-disabled);
}
.pcanvas__mini-node.is-selected {
  fill: var(--vip-brand-500);
}
</style>
