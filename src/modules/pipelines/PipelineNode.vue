<script setup lang="ts">
import { computed } from 'vue'
import type { NodeExecStatus, PipelineNode, ValidationIssue } from '@/shared/types/pipeline'
import { NODE_TYPES } from './nodeTypes'
import VipIcon from '@/shared/ui/VipIcon.vue'

const props = defineProps<{
  node: PipelineNode
  selected: boolean
  issues?: ValidationIssue[]
  execStatus?: NodeExecStatus
}>()

const emit = defineEmits<{
  nodePointerDown: [{ id: string; event: PointerEvent }]
  portPointerDown: [{ nodeId: string; port: string; kind: 'in' | 'out'; event: PointerEvent }]
  portPointerUp: [{ nodeId: string; port: string; kind: 'in' | 'out'; event: PointerEvent }]
}>()

const spec = computed(() => NODE_TYPES[props.node.kind])
const errorCount = computed(() => props.issues?.filter((i) => i.level === 'error').length ?? 0)
const warnCount = computed(() => props.issues?.filter((i) => i.level === 'warning').length ?? 0)
</script>

<template>
  <div
    class="pnode"
    :class="[`is-${spec.category}`, { 'is-selected': selected, 'is-error': errorCount, [`exec-${execStatus}`]: execStatus && execStatus !== 'idle' }]"
    :style="{ left: `${node.x}px`, top: `${node.y}px` }"
    role="button"
    :aria-label="`${spec.label} node: ${node.title}`"
    tabindex="0"
    @pointerdown.stop="emit('nodePointerDown', { id: node.id, event: $event })"
  >
    <!-- input ports -->
    <div class="pnode__ports pnode__ports--in">
      <button
        v-for="p in spec.inputs"
        :key="p.id"
        class="pnode__port"
        :title="p.label"
        :aria-label="`${p.label} input port`"
        @pointerdown.stop="emit('portPointerDown', { nodeId: node.id, port: p.id, kind: 'in', event: $event })"
        @pointerup.stop="emit('portPointerUp', { nodeId: node.id, port: p.id, kind: 'in', event: $event })"
      />
    </div>

    <div class="pnode__head">
      <span class="pnode__icon"><VipIcon :name="spec.icon" :size="15" /></span>
      <span class="pnode__title">{{ node.title }}</span>
      <span v-if="execStatus === 'running'" class="pnode__spin" />
      <VipIcon v-else-if="execStatus === 'succeeded'" name="success" :size="14" class="pnode__exec-icon is-ok" />
      <VipIcon v-else-if="execStatus === 'failed'" name="error" :size="14" class="pnode__exec-icon is-fail" />
    </div>
    <div class="pnode__body">{{ spec.label }}</div>

    <!-- validation marker -->
    <div v-if="errorCount || warnCount" class="pnode__badge" :class="errorCount ? 'is-error' : 'is-warn'" :title="issues?.map((i) => i.message).join('\n')">
      <VipIcon :name="errorCount ? 'error' : 'warning'" :size="12" />
      {{ errorCount || warnCount }}
    </div>

    <!-- output ports -->
    <div class="pnode__ports pnode__ports--out">
      <button
        v-for="p in spec.outputs"
        :key="p.id"
        class="pnode__port is-out"
        :title="p.label"
        :aria-label="`${p.label} output port`"
        @pointerdown.stop="emit('portPointerDown', { nodeId: node.id, port: p.id, kind: 'out', event: $event })"
        @pointerup.stop="emit('portPointerUp', { nodeId: node.id, port: p.id, kind: 'out', event: $event })"
      />
    </div>
  </div>
</template>

<style scoped>
.pnode {
  position: absolute;
  width: 176px;
  background: var(--vip-surface-1);
  border: 1px solid var(--vip-border-strong);
  border-radius: var(--vip-radius-md);
  box-shadow: var(--vip-shadow-sm);
  cursor: grab;
  user-select: none;
  border-left-width: 3px;
}
.pnode:active { cursor: grabbing; }
.pnode.is-source { border-left-color: var(--vip-viz-2, #22c1a6); }
.pnode.is-transform { border-left-color: var(--vip-brand-500); }
.pnode.is-output { border-left-color: var(--vip-viz-3, #f2a93b); }
.pnode.is-selected { border-color: var(--vip-brand-500); box-shadow: 0 0 0 2px var(--vip-brand-soft), var(--vip-shadow-md); }
.pnode.is-error { border-color: var(--vip-danger); }

.pnode.exec-running { box-shadow: 0 0 0 2px var(--vip-info-soft), var(--vip-shadow-md); }
.pnode.exec-succeeded { border-left-color: var(--vip-success); }
.pnode.exec-failed { border-color: var(--vip-danger); }

.pnode__head { display: flex; align-items: center; gap: var(--vip-sp-3); padding: var(--vip-sp-4) var(--vip-sp-5) var(--vip-sp-2); }
.pnode__icon { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; border-radius: var(--vip-radius-sm); background: var(--vip-surface-3); color: var(--vip-text-secondary); flex: none; }
.pnode__title { font-size: var(--vip-fs-sm); font-weight: var(--vip-fw-semibold); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pnode__body { padding: 0 var(--vip-sp-5) var(--vip-sp-4); font-size: var(--vip-fs-2xs); color: var(--vip-text-muted); text-transform: uppercase; letter-spacing: var(--vip-ls-wide); }

.pnode__ports { position: absolute; top: 0; bottom: 0; display: flex; flex-direction: column; justify-content: center; gap: var(--vip-sp-3); }
.pnode__ports--in { left: -7px; }
.pnode__ports--out { right: -7px; }
.pnode__port {
  width: 13px; height: 13px; padding: 0;
  border-radius: 50%;
  background: var(--vip-surface-1);
  border: 2px solid var(--vip-text-muted);
  cursor: crosshair;
  transition: transform var(--vip-motion-fast), border-color var(--vip-motion-fast), background var(--vip-motion-fast);
}
.pnode__port:hover { transform: scale(1.25); border-color: var(--vip-brand-500); background: var(--vip-brand-500); }
.pnode__port.is-out { border-color: var(--vip-brand-400); }

.pnode__badge {
  position: absolute; top: -9px; right: 22px;
  display: inline-flex; align-items: center; gap: 2px;
  padding: 1px 5px; border-radius: var(--vip-radius-full);
  font-size: var(--vip-fs-2xs); font-weight: var(--vip-fw-bold); color: #fff;
}
.pnode__badge.is-error { background: var(--vip-danger); }
.pnode__badge.is-warn { background: var(--vip-warning); }

.pnode__spin { width: 13px; height: 13px; border: 2px solid var(--vip-info); border-right-color: transparent; border-radius: 50%; animation: pn-spin 0.7s linear infinite; }
.pnode__exec-icon.is-ok { color: var(--vip-success-text); }
.pnode__exec-icon.is-fail { color: var(--vip-danger-text); }
@keyframes pn-spin { to { transform: rotate(360deg); } }
</style>
