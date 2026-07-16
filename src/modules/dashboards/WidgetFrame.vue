<script setup lang="ts">
import { computed, toRef } from 'vue'
import type { DashboardWidget } from '@/shared/types/dashboard'
import type { QueryFilter } from '@/shared/types/semantic'
import { useWidgetData } from './useWidgetData'
import VisualRenderer from '@/shared/viz/VisualRenderer.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'

const props = defineProps<{
  widget: DashboardWidget
  crossFilters: QueryFilter[]
  editable?: boolean
  selected?: boolean
}>()
const emit = defineEmits<{
  crossFilter: [{ field: string; value: string }]
  duplicate: []
  delete: []
  edit: []
}>()

const widgetRef = toRef(props, 'widget')
const filtersRef = toRef(props, 'crossFilters')
const { result, loading, error } = useWidgetData(widgetRef, filtersRef)

const showChrome = computed(() => props.widget.format.showTitle && props.widget.type !== 'text' && props.widget.type !== 'image')

const menuItems = [
  { key: 'edit', label: 'Edit visual', icon: 'settings' },
  { key: 'duplicate', label: 'Duplicate', icon: 'duplicate' },
  { key: 'export', label: 'Export data', icon: 'download' },
  { key: 'divider', label: '', divider: true },
  { key: 'delete', label: 'Delete', icon: 'trash', danger: true },
]
function onMenu(key: string) {
  if (key === 'edit') emit('edit')
  else if (key === 'duplicate') emit('duplicate')
  else if (key === 'delete') emit('delete')
}
</script>

<template>
  <div
    class="wframe"
    :class="{ 'is-selected': selected && editable, 'no-border': !widget.format.border }"
    :style="{ background: widget.format.background || 'var(--vip-surface-1)', padding: `${widget.format.padding}px` }"
  >
    <header v-if="showChrome" class="wframe__head">
      <div class="wframe__titles">
        <div class="wframe__title">{{ widget.format.title || widget.general.name }}</div>
        <div v-if="widget.format.subtitle" class="wframe__sub">{{ widget.format.subtitle }}</div>
      </div>
      <div class="wframe__actions" @pointerdown.stop>
        <span v-if="widget.interactions.crossFilter" class="wframe__badge" title="Cross-filtering enabled"><VipIcon name="filter" :size="11" /></span>
        <VipMenu v-if="editable" :items="menuItems" @select="onMenu">
          <template #trigger><button class="wframe__menu" aria-label="Widget menu"><VipIcon name="dotsV" :size="15" /></button></template>
        </VipMenu>
      </div>
    </header>

    <div class="wframe__body">
      <VisualRenderer
        :widget="widget"
        :result="result"
        :loading="loading"
        :error="error"
        :interactive="!editable"
        @cross-filter="emit('crossFilter', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.wframe {
  width: 100%; height: 100%;
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  display: flex; flex-direction: column; overflow: hidden;
  transition: border-color var(--vip-motion-fast), box-shadow var(--vip-motion-fast);
}
.wframe.no-border { border-color: transparent; }
.wframe.is-selected { border-color: var(--vip-brand-500); box-shadow: 0 0 0 2px var(--vip-brand-soft); }
.wframe__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--vip-sp-3); margin-bottom: var(--vip-sp-4); flex: none; }
.wframe__title { font-size: var(--vip-fs-md); font-weight: var(--vip-fw-semibold); }
.wframe__sub { font-size: var(--vip-fs-xs); color: var(--vip-text-muted); margin-top: 1px; }
.wframe__actions { display: flex; align-items: center; gap: var(--vip-sp-2); }
.wframe__badge { color: var(--vip-text-disabled); display: inline-flex; }
.wframe__menu { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; background: none; border: none; border-radius: var(--vip-radius-sm); color: var(--vip-text-muted); }
.wframe__menu:hover { background: var(--vip-surface-hover); color: var(--vip-text-primary); }
.wframe__body { flex: 1; min-height: 0; }
</style>
