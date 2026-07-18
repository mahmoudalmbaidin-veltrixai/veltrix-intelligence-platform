<script setup lang="ts">
import { ref, computed } from 'vue'
import type { DashboardEditor } from './useDashboardEditor'
import { GRID_COLS } from './useDashboardEditor'
import type { DashboardWidget, GridPosition } from '@/shared/types/dashboard'
import type { QueryFilter } from '@/shared/types/semantic'
import WidgetFrame from './WidgetFrame.vue'

const props = defineProps<{
  editor: DashboardEditor
  crossFilters: QueryFilter[]
  editable?: boolean
  rowHeight?: number
}>()

const emit = defineEmits<{ crossFilter: [{ field: string; value: string }] }>()

const rowH = computed(() => props.rowHeight ?? 76)
const gap = 10
const gridRef = ref<HTMLElement>()

// Unwrapped accessors — the editor's computed refs aren't auto-unwrapped
// when read through a prop object.
const widgets = computed(() => props.editor.widgets.value)
const selectedId = computed(() => props.editor.selectedId.value)

function colWidth(): number {
  const w = gridRef.value?.clientWidth ?? 1200
  return (w - gap * (GRID_COLS - 1)) / GRID_COLS
}

function styleFor(pos: GridPosition) {
  const cw = colWidth()
  return {
    transform: `translate(${pos.x * (cw + gap)}px, ${pos.y * (rowH.value + gap)}px)`,
    width: `${pos.w * cw + (pos.w - 1) * gap}px`,
    height: `${pos.h * rowH.value + (pos.h - 1) * gap}px`,
  }
}

const gridHeight = computed(() => {
  const maxY = widgets.value.reduce((m, w) => Math.max(m, w.pos.y + w.pos.h), 8)
  return (maxY + 2) * (rowH.value + gap)
})

/* ---- drag / resize ---- */
let action: 'move' | 'resize' | null = null
let activeId = ''
let startPos = { x: 0, y: 0 }
let startGrid: GridPosition = { x: 0, y: 0, w: 0, h: 0 }

function clamp(pos: GridPosition): GridPosition {
  const x = Math.max(0, Math.min(GRID_COLS - pos.w, pos.x))
  return { ...pos, x, y: Math.max(0, pos.y) }
}

function onMoveStart(w: DashboardWidget, e: PointerEvent) {
  if (!props.editable || w.general.locked) { props.editor.select(w.id); return }
  props.editor.select(w.id)
  props.editor.beginChange()
  action = 'move'
  activeId = w.id
  startPos = { x: e.clientX, y: e.clientY }
  startGrid = { ...w.pos }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onEnd)
}
function onResizeStart(w: DashboardWidget, e: PointerEvent) {
  if (!props.editable || w.general.locked) return
  e.stopPropagation()
  props.editor.select(w.id)
  props.editor.beginChange()
  action = 'resize'
  activeId = w.id
  startPos = { x: e.clientX, y: e.clientY }
  startGrid = { ...w.pos }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onEnd)
}
function onMove(e: PointerEvent) {
  const cw = colWidth()
  const dx = Math.round((e.clientX - startPos.x) / (cw + gap))
  const dy = Math.round((e.clientY - startPos.y) / (rowH.value + gap))
  if (action === 'move') {
    props.editor.updatePosition(activeId, clamp({ ...startGrid, x: startGrid.x + dx, y: startGrid.y + dy }))
  } else if (action === 'resize') {
    const w = Math.max(2, Math.min(GRID_COLS - startGrid.x, startGrid.w + dx))
    const h = Math.max(2, startGrid.h + dy)
    props.editor.updatePosition(activeId, { ...startGrid, w, h })
  }
}
function onEnd() {
  action = null
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onEnd)
}
</script>

<template>
  <div
    ref="gridRef"
    class="dgrid"
    :class="{ 'is-editable': editable }"
    :style="{ height: `${gridHeight}px` }"
    @pointerdown.self="editor.select(null)"
  >
    <!-- grid backdrop -->
    <div v-if="editable" class="dgrid__lines" :style="{ backgroundSize: `${(100 / GRID_COLS)}% ${rowHeight ?? 76}px` }" />

    <div
      v-for="w in widgets"
      :key="w.id"
      class="dgrid__item"
      :class="{ 'is-selected': selectedId === w.id && editable, 'is-hidden': !w.general.visible }"
      :style="styleFor(w.pos)"
      :tabindex="editable ? 0 : -1"
      :role="editable ? 'button' : undefined"
      :aria-label="editable ? `${w.general.name} widget${selectedId === w.id ? ', selected' : ''}. Enter to select, arrow keys to move, Shift plus arrows to resize, Delete to remove.` : undefined"
      :aria-pressed="editable ? selectedId === w.id : undefined"
      @pointerdown="onMoveStart(w, $event)"
      @keydown.enter.prevent="editable && editor.select(w.id)"
      @keydown.space.prevent="editable && editor.select(w.id)"
    >
      <WidgetFrame
        :widget="w"
        :cross-filters="crossFilters"
        :editable="editable"
        :selected="selectedId === w.id"
        @cross-filter="emit('crossFilter', $event)"
        @duplicate="editor.duplicateWidget(w.id)"
        @delete="editor.deleteWidget(w.id)"
        @edit="editor.select(w.id)"
      />
      <div v-if="editable && !w.general.locked" class="dgrid__resize" @pointerdown="onResizeStart(w, $event)" />
    </div>
  </div>
</template>

<style scoped>
.dgrid { position: relative; width: 100%; min-height: 400px; }
.dgrid__lines {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(to right, var(--vip-grid-line) 1px, transparent 1px),
    linear-gradient(to bottom, var(--vip-grid-line) 1px, transparent 1px);
  pointer-events: none;
}
.dgrid__item { position: absolute; top: 0; left: 0; transition: box-shadow var(--vip-motion-fast); }
.dgrid.is-editable .dgrid__item { cursor: grab; }
.dgrid.is-editable .dgrid__item:active { cursor: grabbing; }
.dgrid__item.is-selected { z-index: 3; }
.dgrid__item.is-hidden { opacity: 0.4; }
.dgrid__resize {
  position: absolute; right: 0; bottom: 0; width: 16px; height: 16px;
  cursor: nwse-resize; z-index: 4;
  background: linear-gradient(135deg, transparent 50%, var(--vip-border-strong) 50%);
  border-bottom-right-radius: var(--vip-radius-lg);
}
</style>
