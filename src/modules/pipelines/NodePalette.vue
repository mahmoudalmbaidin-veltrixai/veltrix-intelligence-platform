<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PipelineNodeKind } from '@/shared/types/pipeline'
import { NODE_TYPES, PALETTE_GROUPS } from './nodeTypes'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipInput from '@/shared/ui/VipInput.vue'

const emit = defineEmits<{ add: [PipelineNodeKind] }>()
const search = ref('')

const groups = computed(() => {
  const q = search.value.trim().toLowerCase()
  return PALETTE_GROUPS.map((g) => ({
    label: g.label,
    kinds: g.kinds.filter((k) => !q || NODE_TYPES[k].label.toLowerCase().includes(q) || NODE_TYPES[k].description.toLowerCase().includes(q)),
  })).filter((g) => g.kinds.length)
})

function onDragStart(e: DragEvent, kind: PipelineNodeKind) {
  e.dataTransfer?.setData('application/vip-node', kind)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <aside class="palette">
    <div class="palette__search">
      <VipInput v-model="search" icon="search" placeholder="Search nodes…" size="sm" />
    </div>
    <div class="palette__scroll">
      <div v-for="g in groups" :key="g.label" class="palette__group">
        <div class="palette__group-label">{{ g.label }}</div>
        <button
          v-for="kind in g.kinds"
          :key="kind"
          class="palette__node"
          :class="`is-${NODE_TYPES[kind].category}`"
          draggable="true"
          :title="`${NODE_TYPES[kind].description} — press Enter to add`"
          :aria-label="`Add ${NODE_TYPES[kind].label} node`"
          @dragstart="onDragStart($event, kind)"
          @dblclick="emit('add', kind)"
          @keydown.enter.prevent="emit('add', kind)"
          @keydown.space.prevent="emit('add', kind)"
        >
          <span class="palette__node-icon"><VipIcon :name="NODE_TYPES[kind].icon" :size="15" /></span>
          <span class="palette__node-text">
            <span class="palette__node-title">{{ NODE_TYPES[kind].label }}</span>
            <span class="palette__node-desc">{{ NODE_TYPES[kind].description }}</span>
          </span>
          <VipIcon name="drag" :size="14" class="palette__node-grip" />
        </button>
      </div>
    </div>
    <div class="palette__hint">Drag onto canvas or double-click to add</div>
  </aside>
</template>

<style scoped>
.palette { display: flex; flex-direction: column; height: 100%; background: var(--vip-surface-1); }
.palette__search { padding: var(--vip-sp-5); border-bottom: 1px solid var(--vip-border-subtle); }
.palette__scroll { flex: 1; overflow-y: auto; padding: var(--vip-sp-5); }
.palette__group { margin-bottom: var(--vip-sp-6); }
.palette__group-label { font-size: var(--vip-fs-2xs); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); color: var(--vip-text-disabled); margin-bottom: var(--vip-sp-3); }
.palette__node {
  display: flex; align-items: center; gap: var(--vip-sp-4); width: 100%;
  padding: var(--vip-sp-4); margin-bottom: var(--vip-sp-2);
  background: var(--vip-surface-2); border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-md); text-align: left; cursor: grab;
  border-left-width: 3px;
}
.palette__node:hover { border-color: var(--vip-border-strong); background: var(--vip-surface-hover); }
.palette__node:active { cursor: grabbing; }
.palette__node.is-source { border-left-color: var(--vip-viz-2, #22c1a6); }
.palette__node.is-transform { border-left-color: var(--vip-brand-500); }
.palette__node.is-output { border-left-color: var(--vip-viz-3, #f2a93b); }
.palette__node-icon { width: 26px; height: 26px; flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: var(--vip-radius-sm); background: var(--vip-surface-3); color: var(--vip-text-secondary); }
.palette__node-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.palette__node-title { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-medium); }
.palette__node-desc { font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.palette__node-grip { color: var(--vip-text-disabled); }
.palette__hint { padding: var(--vip-sp-4); border-top: 1px solid var(--vip-border-subtle); font-size: var(--vip-fs-2xs); color: var(--vip-text-disabled); text-align: center; }
</style>
