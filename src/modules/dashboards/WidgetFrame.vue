<script setup lang="ts">
import { computed, toRef } from 'vue'
import type { Dashboard, DashboardWidget } from '@/shared/types/dashboard'
import type { QueryFilter } from '@/shared/types/semantic'
import { useWidgetData } from './useWidgetData'
import { validateWidgetConfiguration } from './widgetValidation'
import VisualRenderer from '@/shared/viz/VisualRenderer.vue'
import VipIcon from '@/shared/ui/VipIcon.vue'
import VipMenu from '@/shared/ui/VipMenu.vue'

const props = defineProps<{
  widget: DashboardWidget
  dashboard: Dashboard
  crossFilters: QueryFilter[]
  editable?: boolean
  draftPreview?: boolean
  selected?: boolean
}>()
const emit = defineEmits<{
  crossFilter: [{ field: string; value: string }]
  duplicate: []
  delete: []
  edit: []
}>()

const widgetRef = toRef(props, 'widget')
const dashboardRef = toRef(props, 'dashboard')
const filtersRef = toRef(props, 'crossFilters')
const previewRef = computed(() => Boolean(props.draftPreview ?? props.editable))
const { result, loading, error } = useWidgetData(dashboardRef, widgetRef, filtersRef, previewRef)

const showChrome = computed(
  () => props.widget.format.showTitle && props.widget.type !== 'text' && props.widget.type !== 'image',
)

// In the editor, a data widget missing its model/measure is shown as an
// intentional "needs configuration" call-to-action rather than a broken chart
// (which would otherwise be saved and rejected by the backend with a 422).
const validation = computed(() => validateWidgetConfiguration(props.widget))
const incomplete = computed(() => Boolean(props.editable) && !validation.value.valid)

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
        <span v-if="widget.interactions.crossFilter" class="wframe__badge" title="Cross-filtering enabled"
          ><VipIcon name="filter" :size="11"
        /></span>
        <VipMenu v-if="editable" :items="menuItems" @select="onMenu">
          <template #trigger
            ><button class="wframe__menu" aria-label="Widget menu"><VipIcon name="dotsV" :size="15" /></button
          ></template>
        </VipMenu>
      </div>
    </header>

    <div class="wframe__body">
      <button v-if="incomplete" type="button" class="wframe__incomplete" @click="emit('edit')" @pointerdown.stop>
        <VipIcon name="settings" :size="20" class="wframe__incomplete-icon" />
        <span class="wframe__incomplete-title">Needs configuration</span>
        <span class="wframe__incomplete-hint">{{ validation.missing.join(' · ') }}</span>
        <span class="wframe__incomplete-cta">Configure widget</span>
      </button>
      <VisualRenderer
        v-else
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
  width: 100%;
  height: 100%;
  border: 1px solid var(--vip-border-subtle);
  border-radius: var(--vip-radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition:
    border-color var(--vip-motion-fast),
    box-shadow var(--vip-motion-fast);
}
.wframe.no-border {
  border-color: transparent;
}
.wframe.is-selected {
  border-color: var(--vip-brand-500);
  box-shadow: 0 0 0 2px var(--vip-brand-soft);
}
.wframe__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--vip-sp-3);
  margin-bottom: var(--vip-sp-4);
  flex: none;
}
.wframe__title {
  font-size: var(--vip-fs-md);
  font-weight: var(--vip-fw-semibold);
}
.wframe__sub {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
  margin-top: 1px;
}
.wframe__actions {
  display: flex;
  align-items: center;
  gap: var(--vip-sp-2);
}
.wframe__badge {
  color: var(--vip-text-disabled);
  display: inline-flex;
}
.wframe__menu {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--vip-radius-sm);
  color: var(--vip-text-muted);
}
.wframe__menu:hover {
  background: var(--vip-surface-hover);
  color: var(--vip-text-primary);
}
.wframe__body {
  flex: 1;
  min-height: 0;
}
.wframe__incomplete {
  width: 100%;
  height: 100%;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--vip-sp-2);
  text-align: center;
  padding: var(--vip-sp-4);
  background: var(--vip-surface-2);
  border: 1px dashed var(--vip-border-strong);
  border-radius: var(--vip-radius-md);
  color: var(--vip-text-secondary);
  cursor: pointer;
}
.wframe__incomplete:hover {
  border-color: var(--vip-brand-500);
}
.wframe__incomplete:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--vip-brand-soft);
}
.wframe__incomplete-icon {
  color: var(--vip-text-muted);
}
.wframe__incomplete-title {
  font-size: var(--vip-fs-sm);
  font-weight: var(--vip-fw-semibold);
  color: var(--vip-text-primary);
}
.wframe__incomplete-hint {
  font-size: var(--vip-fs-xs);
  color: var(--vip-text-muted);
}
.wframe__incomplete-cta {
  margin-top: var(--vip-sp-2);
  font-size: var(--vip-fs-xs);
  font-weight: var(--vip-fw-medium);
  color: var(--vip-brand-text);
}
</style>
